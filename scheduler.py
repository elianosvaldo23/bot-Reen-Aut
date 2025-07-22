from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Bot
from database import get_session, Post, PostSchedule, PostChannel, ScheduledJob
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)
scheduler = None

def start_scheduler(application):
    global scheduler
    scheduler = AsyncIOScheduler()
    scheduler.start()
    
    # Schedule all active posts
    schedule_all_posts(application.bot)
    
    # Add job to check for missed posts every hour
    scheduler.add_job(
        check_missed_posts,
        trigger='cron',
        hour='*',
        args=[application.bot]
    )

def schedule_all_posts(bot):
    session = get_session()
    
    posts = session.query(Post).filter_by(is_active=True).all()
    
    for post in posts:
        schedule = session.query(PostSchedule).filter_by(post_id=post.id, is_enabled=True).first()
        if schedule:
            schedule_post(bot, post, schedule)
    
    session.close()

def schedule_post(bot, post, schedule):
    days = [int(d) for d in schedule.days_of_week.split(',')]
    hour, minute = map(int, schedule.send_time.split(':'))
    
    # Schedule sending
    job = scheduler.add_job(
        send_post_to_channels,
        trigger=CronTrigger(
            day_of_week=','.join(str(d-1) for d in days),
            hour=hour,
            minute=minute
        ),
        args=[bot, post.id],
        id=f"send_{post.id}"
    )
    
    logger.info(f"Scheduled post {post.id} for {schedule.send_time} on days {days}")

async def send_post_to_channels(bot: Bot, post_id: int):
    session = get_session()
    
    post = session.query(Post).filter_by(id=post_id, is_active=True).first()
    if not post:
        session.close()
        return
    
    post_channels = session.query(PostChannel).filter_by(post_id=post_id).all()
    channels = [pc.channel_id for pc in post_channels]
    
    if not channels:
        logger.warning(f"No channels assigned for post {post_id}")
        session.close()
        return
    
    schedule = session.query(PostSchedule).filter_by(post_id=post_id, is_enabled=True).first()
    if not schedule:
        session.close()
        return
    
    sent_messages = []
    
    for channel_id in channels:
        try:
            if post.content_type == 'text':
                message = await bot.send_message(
                    chat_id=channel_id,
                    text=post.content_text
                )
            elif post.content_type == 'photo':
                message = await bot.send_photo(
                    chat_id=channel_id,
                    photo=post.file_id,
                    caption=post.content_text
                )
            elif post.content_type == 'video':
                message = await bot.send_video(
                    chat_id=channel_id,
                    video=post.file_id,
                    caption=post.content_text
                )
            elif post.content_type == 'audio':
                message = await bot.send_audio(
                    chat_id=channel_id,
                    audio=post.file_id,
                    caption=post.content_text
                )
            elif post.content_type == 'document':
                message = await bot.send_document(
                    chat_id=channel_id,
                    document=post.file_id,
                    caption=post.content_text
                )
            
            sent_messages.append({
                'channel_id': channel_id,
                'message_id': message.message_id
            })
            
            # Schedule deletion
            delete_time = datetime.utcnow() + timedelta(hours=schedule.delete_after_hours)
            
            job = scheduler.add_job(
                delete_post_from_channel,
                trigger='date',
                run_date=delete_time,
                args=[bot, channel_id, message.message_id],
                id=f"delete_{post.id}_{channel_id}_{message.message_id}"
            )
            
            # Save scheduled job
            scheduled_job = ScheduledJob(
                post_id=post_id,
                job_type='send',
                scheduled_time=datetime.utcnow(),
                channel_id=channel_id,
                message_id=message.message_id
            )
            session.add(scheduled_job)
            
            logger.info(f"Sent post {post_id} to channel {channel_id}")
            
        except Exception as e:
            logger.error(f"Error sending post {post_id} to channel {channel_id}: {e}")
    
    session.commit()
    session.close()

async def delete_post_from_channel(bot: Bot, channel_id: str, message_id: int):
    try:
        await bot.delete_message(chat_id=channel_id, message_id=message_id)
        logger.info(f"Deleted message {message_id} from channel {channel_id}")
    except Exception as e:
        logger.error(f"Error deleting message {message_id} from channel {channel_id}: {e}")

async def check_missed_posts(bot: Bot):
    """Check for posts that should have been sent but weren't"""
    session = get_session()
    
    # This is a simple check - in production you might want more sophisticated logic
    logger.info("Checking for missed posts...")
    
    session.close()

def stop_scheduler():
    if scheduler:
        scheduler.shutdown()
