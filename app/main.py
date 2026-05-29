from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime, date
import shutil
import uuid
import os
import requests

from PIL import Image, ImageDraw, ImageFont
from moviepy import ImageClip, concatenate_videoclips

from dotenv import load_dotenv
from qcloud_cos import CosConfig, CosS3Client

load_dotenv()

SECRET_ID = os.getenv("TENCENT_SECRET_ID")
SECRET_KEY = os.getenv("TENCENT_SECRET_KEY")
REGION = os.getenv("TENCENT_REGION")
BUCKET = os.getenv("TENCENT_BUCKET")

config = CosConfig(Region=REGION, SecretId=SECRET_ID, SecretKey=SECRET_KEY)
client = CosS3Client(config)

app = FastAPI(title="守护派派")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.join(BASE_DIR, "..")
UPLOAD_DIR = os.path.join(PROJECT_DIR, "uploads")
VIDEO_DIR = os.path.join(PROJECT_DIR, "videos")
FRAME_DIR = os.path.join(VIDEO_DIR, "frames")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(VIDEO_DIR, exist_ok=True)
os.makedirs(FRAME_DIR, exist_ok=True)

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.mount("/videos", StaticFiles(directory=VIDEO_DIR), name="videos")

DATABASE_URL = "sqlite:///./paipai.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Media(Base):
    __tablename__ = "media"

    id = Column(Integer, primary_key=True, index=True)
    baby_id = Column(Integer)
    media_type = Column(String)
    file_path = Column(String)
    note = Column(String)
    created_at = Column(DateTime, default=datetime.now)


class Milestone(Base):
    __tablename__ = "milestones"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    description = Column(String)
    event_date = Column(String)
    created_at = Column(DateTime, default=datetime.now)


Base.metadata.create_all(bind=engine)


BABY_NAME = "派派"
BABY_BIRTHDAY = date(2026, 2, 13)


def baby_age_text(target_date):
    if isinstance(target_date, datetime):
        target_date = target_date.date()

    if isinstance(target_date, str):
        target_date = datetime.strptime(target_date, "%Y-%m-%d").date()

    days = (target_date - BABY_BIRTHDAY).days + 1

    if days < 1:
        days = 1

    months = (target_date.year - BABY_BIRTHDAY.year) * 12 + target_date.month - BABY_BIRTHDAY.month

    if target_date.day < BABY_BIRTHDAY.day:
        months -= 1

    month_start_year = BABY_BIRTHDAY.year + (BABY_BIRTHDAY.month + months - 1) // 12
    month_start_month = (BABY_BIRTHDAY.month + months - 1) % 12 + 1
    month_start_day = min(BABY_BIRTHDAY.day, 28)

    month_start = date(month_start_year, month_start_month, month_start_day)
    extra_days = (target_date - month_start).days

    if months <= 0:
        return f"第{days}天"

    return f"第{days}天（{months}个月{extra_days}天）"


def get_font(size):
    font_paths = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/Library/Fonts/Arial Unicode.ttf"
    ]

    for path in font_paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)

    return ImageFont.load_default()


def create_video_frame(image_path, note, created_at, output_path):
    width = 1080
    height = 1920

    background = Image.new("RGB", (width, height), (245, 245, 245))

    image = Image.open(image_path).convert("RGB")
    image.thumbnail((1000, 1350))

    x = (width - image.width) // 2
    y = 160

    background.paste(image, (x, y))

    draw = ImageDraw.Draw(background)

    title_font = get_font(56)
    text_font = get_font(42)
    small_font = get_font(34)

    upload_date = created_at.date()
    age_text = baby_age_text(upload_date)

    title = "守护派派成长记录"
    note_text = note or "宝宝成长照片"
    date_text = f"📅 {upload_date}"
    age_line = f"👶 {age_text}"

    draw.text((80, 40), title, fill=(20, 20, 20), font=title_font)
    draw.text((80, 1540), note_text, fill=(20, 20, 20), font=text_font)
    draw.text((80, 1620), date_text, fill=(90, 90, 90), font=small_font)
    draw.text((80, 1680), age_line, fill=(90, 90, 90), font=small_font)

    background.save(output_path)


@app.get("/", response_class=HTMLResponse)
def root():
    db = SessionLocal()
    photo_count = db.query(Media).count()
    milestone_count = db.query(Milestone).count()
    latest = db.query(Milestone).order_by(Milestone.event_date.desc()).first()
    db.close()

    latest_text = latest.title if latest else "还没有里程碑"

    return f"""
    <html>
    <head>
        <title>守护派派</title>
        <style>
            body {{
                font-family: Arial;
                background: #f5f5f5;
                padding: 30px;
                text-align: center;
            }}
            .box {{
                max-width: 700px;
                margin: 60px auto;
                background: white;
                padding: 30px;
                border-radius: 18px;
                box-shadow: 0 4px 14px rgba(0,0,0,0.12);
            }}
            .stat {{
                font-size: 22px;
                margin: 16px 0;
            }}
            a {{
                display: inline-block;
                margin: 10px;
                padding: 14px 22px;
                background: #1677ff;
                color: white;
                text-decoration: none;
                border-radius: 10px;
                font-size: 18px;
            }}
            .video {{
                background: #52c41a;
            }}
        </style>
    </head>
    <body>
        <div class="box">
            <h1>守护派派 👶</h1>
            <div class="stat">派派今天 {baby_age_text(date.today())}</div>
            <div class="stat">已保存照片：{photo_count} 张</div>
            <div class="stat">成长里程碑：{milestone_count} 条</div>
            <div class="stat">最新里程碑：{latest_text}</div>

            <a href="/upload">上传照片</a>
            <a href="/gallery">查看相册</a>
            <a href="/timeline">成长时间轴</a>
            <a class="video" href="/video">成长视频</a>
        </div>
    </body>
    </html>
    """


@app.get("/upload", response_class=HTMLResponse)
def upload_page():
    return """
    <html>
    <head>
        <title>守护派派 - 上传照片</title>
        <style>
            body { font-family: Arial; background: #f6f6f6; padding: 30px; }
            .box {
                max-width: 500px;
                margin: 60px auto;
                background: white;
                padding: 30px;
                border-radius: 18px;
                box-shadow: 0 4px 14px rgba(0,0,0,0.12);
            }
            h1 { text-align: center; }
            input, textarea, button {
                width: 100%;
                margin-top: 12px;
                padding: 12px;
                font-size: 16px;
                box-sizing: border-box;
            }
            button {
                background: #1677ff;
                color: white;
                border: none;
                border-radius: 10px;
                cursor: pointer;
            }
            button:disabled { background: gray; }
            a { display: block; text-align: center; margin-top: 20px; }
        </style>
    </head>
    <body>
        <div class="box">
            <h1>上传照片 👶</h1>

            <form id="uploadForm" action="/upload-photo" method="post" enctype="multipart/form-data">
                <input type="hidden" name="baby_id" value="1">

                <label>照片备注</label>
                <textarea name="note" placeholder="例如：第一次翻身、今天笑了、晚上睡前"></textarea>

                <label>选择照片</label>
                <input type="file" name="file" accept="image/*" required>

                <button id="uploadBtn" type="submit">上传照片</button>
            </form>

            <a href="/">返回首页</a>
            <a href="/gallery">查看宝宝相册</a>
        </div>

        <script>
            const form = document.getElementById("uploadForm");
            const btn = document.getElementById("uploadBtn");

            form.addEventListener("submit", function () {
                btn.disabled = true;
                btn.innerText = "正在上传，请稍等...";
            });
        </script>
    </body>
    </html>
    """


@app.post("/upload-photo")
async def upload_photo(
    baby_id: int = Form(1),
    note: str = Form(""),
    file: UploadFile = File(...)
):
    db = SessionLocal()

    ext = file.filename.split(".")[-1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    local_path = os.path.join(UPLOAD_DIR, filename)

    with open(local_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    client.upload_file(
        Bucket=BUCKET,
        LocalFilePath=local_path,
        Key=filename
    )

    cos_url = f"https://{BUCKET}.cos.{REGION}.myqcloud.com/{filename}"

    media = Media(
        baby_id=baby_id,
        media_type="photo",
        file_path=cos_url,
        note=note
    )

    db.add(media)
    db.commit()
    db.refresh(media)
    db.close()

    return HTMLResponse(f"""
    <html>
    <head>
        <title>上传成功</title>
        <style>
            body {{
                font-family: Arial;
                background: #f6f6f6;
                text-align: center;
                padding: 60px;
            }}
            .box {{
                background: white;
                padding: 30px;
                border-radius: 18px;
                max-width: 500px;
                margin: auto;
                box-shadow: 0 4px 14px rgba(0,0,0,0.12);
            }}
            a {{
                display: block;
                margin-top: 20px;
                font-size: 18px;
            }}
        </style>
    </head>
    <body>
        <div class="box">
            <h1>上传成功 🎉</h1>
            <p>{note}</p>
            <a href="/gallery">查看宝宝相册</a>
            <a href="/upload">继续上传</a>
            <a href="/">返回首页</a>
        </div>
    </body>
    </html>
    """)


@app.get("/video", response_class=HTMLResponse)
def video_page():
    video_path = os.path.join(VIDEO_DIR, "paipai_growth.mp4")
    has_video = os.path.exists(video_path)

    download_html = ""

    if has_video:
        download_html = """
        <a class="download" href="/download-video">下载成长视频</a>
        <video controls width="100%" style="margin-top:20px; border-radius:12px;">
            <source src="/videos/paipai_growth.mp4" type="video/mp4">
        </video>
        """

    return f"""
    <html>
    <head>
        <title>派派成长视频</title>
        <style>
            body {{
                font-family: Arial;
                background: #f5f5f5;
                padding: 30px;
                text-align: center;
            }}
            .box {{
                max-width: 700px;
                margin: 60px auto;
                background: white;
                padding: 30px;
                border-radius: 18px;
                box-shadow: 0 4px 14px rgba(0,0,0,0.12);
            }}
            a, button {{
                display: inline-block;
                margin: 10px;
                padding: 14px 22px;
                background: #1677ff;
                color: white;
                text-decoration: none;
                border: none;
                border-radius: 10px;
                font-size: 18px;
                cursor: pointer;
            }}
            .download {{
                background: #52c41a;
            }}
        </style>
    </head>
    <body>
        <div class="box">
            <h1>派派成长视频 🎬</h1>
            <p>系统会按照片上传时间自动排序，生成成长纪念视频。</p>

            <form action="/generate-video" method="post">
                <button type="submit">生成成长视频</button>
            </form>

            <a href="/">返回首页</a>
            <a href="/gallery">查看相册</a>

            {download_html}
        </div>
    </body>
    </html>
    """


@app.post("/generate-video")
def generate_video():
    db = SessionLocal()
    media_list = db.query(Media).order_by(Media.created_at.asc()).all()
    db.close()

    if not media_list:
        return HTMLResponse("""
        <h1>还没有照片，无法生成视频</h1>
        <a href="/upload">先去上传照片</a>
        """)

    for file_name in os.listdir(FRAME_DIR):
        file_path = os.path.join(FRAME_DIR, file_name)
        if os.path.isfile(file_path):
            os.remove(file_path)

    clips = []

    for index, item in enumerate(media_list):
        try:
            temp_image_path = os.path.join(FRAME_DIR, f"source_{index}.jpg")
            frame_path = os.path.join(FRAME_DIR, f"frame_{index}.jpg")

            response = requests.get(item.file_path, timeout=20)
            response.raise_for_status()

            with open(temp_image_path, "wb") as f:
                f.write(response.content)

            create_video_frame(
                image_path=temp_image_path,
                note=item.note,
                created_at=item.created_at,
                output_path=frame_path
            )

            clip = ImageClip(frame_path).with_duration(2.5)
            clips.append(clip)

        except Exception as e:
            print(f"生成第 {index + 1} 张照片失败：{e}")

    if not clips:
        return HTMLResponse("""
        <h1>视频生成失败</h1>
        <p>没有可用照片，请检查腾讯云图片是否可以访问。</p>
        <a href="/gallery">返回相册</a>
        """)

    final_video = concatenate_videoclips(clips, method="compose")
    output_path = os.path.join(VIDEO_DIR, "paipai_growth.mp4")

    final_video.write_videofile(
        output_path,
        fps=24,
        codec="libx264",
        audio=False
    )

    final_video.close()

    for clip in clips:
        clip.close()

    return RedirectResponse(url="/video", status_code=303)


@app.get("/download-video")
def download_video():
    video_path = os.path.join(VIDEO_DIR, "paipai_growth.mp4")

    if not os.path.exists(video_path):
        return HTMLResponse("""
        <h1>还没有生成视频</h1>
        <a href="/video">返回生成页面</a>
        """)

    return FileResponse(
        video_path,
        media_type="video/mp4",
        filename="paipai_growth.mp4"
    )


@app.get("/timeline", response_class=HTMLResponse)
def timeline():
    db = SessionLocal()
    milestones = db.query(Milestone).order_by(Milestone.event_date.asc()).all()
    db.close()

    html = """
    <html>
    <head>
        <title>派派成长时间轴</title>
        <style>
            body { font-family: Arial; background: #f5f5f5; padding: 30px; }
            h1 { text-align: center; }
            .top { text-align: center; margin-bottom: 25px; }
            .top a {
                background: #1677ff;
                color: white;
                padding: 12px 18px;
                border-radius: 10px;
                text-decoration: none;
                margin: 6px;
                display: inline-block;
            }
            .box {
                max-width: 700px;
                margin: 0 auto 30px auto;
                background: white;
                padding: 24px;
                border-radius: 18px;
                box-shadow: 0 4px 14px rgba(0,0,0,0.1);
            }
            input, textarea, button {
                width: 100%;
                margin-top: 12px;
                padding: 12px;
                font-size: 16px;
                box-sizing: border-box;
            }
            button {
                background: #1677ff;
                color: white;
                border: none;
                border-radius: 10px;
                cursor: pointer;
            }
            .timeline {
                max-width: 700px;
                margin: auto;
                border-left: 4px solid #1677ff;
                padding-left: 22px;
            }
            .item {
                background: white;
                margin-bottom: 18px;
                padding: 18px;
                border-radius: 14px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.08);
                position: relative;
            }
            .item:before {
                content: "";
                width: 16px;
                height: 16px;
                background: #1677ff;
                border-radius: 50%;
                position: absolute;
                left: -32px;
                top: 22px;
            }
            .date, .age { color: gray; font-size: 14px; }
            .delete { background: #ff4d4f; margin-top: 10px; }
        </style>
    </head>
    <body>
        <h1>派派成长时间轴 👣</h1>

        <div class="top">
            <a href="/">返回首页</a>
            <a href="/gallery">查看相册</a>
        </div>

        <div class="box">
            <h2>添加成长里程碑</h2>
            <form action="/add-milestone" method="post">
                <label>日期</label>
                <input type="date" name="event_date" required>

                <label>标题</label>
                <input type="text" name="title" placeholder="例如：第一次翻身" required>

                <label>描述</label>
                <textarea name="description" placeholder="例如：今天派派自己翻身成功了，全家都很开心"></textarea>

                <button type="submit">添加里程碑</button>
            </form>
        </div>

        <div class="timeline">
    """

    if not milestones:
        html += """
        <div class="item">
            <h2>还没有里程碑</h2>
            <p>先添加一条，比如：出生、满月、100天、第一次翻身。</p>
        </div>
        """

    for item in milestones:
        html += f"""
        <div class="item">
            <div class="date">📅 {item.event_date}</div>
            <div class="age">👶 {baby_age_text(item.event_date)}</div>
            <h2>{item.title}</h2>
            <p>{item.description or ""}</p>

            <form action="/delete-milestone/{item.id}" method="post" onsubmit="return confirm('确定删除这条里程碑吗？');">
                <button class="delete" type="submit">删除</button>
            </form>
        </div>
        """

    html += """
        </div>
    </body>
    </html>
    """

    return html


@app.post("/add-milestone")
def add_milestone(
    event_date: str = Form(...),
    title: str = Form(...),
    description: str = Form("")
):
    db = SessionLocal()

    milestone = Milestone(
        event_date=event_date,
        title=title,
        description=description
    )

    db.add(milestone)
    db.commit()
    db.close()

    return RedirectResponse(url="/timeline", status_code=303)


@app.post("/delete-milestone/{milestone_id}")
def delete_milestone(milestone_id: int):
    db = SessionLocal()
    milestone = db.query(Milestone).filter(Milestone.id == milestone_id).first()

    if milestone:
        db.delete(milestone)
        db.commit()

    db.close()
    return RedirectResponse(url="/timeline", status_code=303)


@app.post("/delete-photo/{media_id}")
def delete_photo(media_id: int):
    db = SessionLocal()
    media = db.query(Media).filter(Media.id == media_id).first()

    if media:
        try:
            cos_key = media.file_path.split(f"{REGION}.myqcloud.com/")[-1]
            client.delete_object(Bucket=BUCKET, Key=cos_key)
        except Exception:
            pass

        db.delete(media)
        db.commit()

    db.close()
    return RedirectResponse(url="/gallery", status_code=303)


@app.get("/gallery", response_class=HTMLResponse)
def gallery():
    db = SessionLocal()
    media_list = db.query(Media).order_by(Media.created_at.desc()).all()
    db.close()

    html = """
    <html>
    <head>
        <title>宝宝成长相册</title>
        <style>
            body { font-family: Arial; background: #f5f5f5; padding: 30px; }
            h1 { text-align: center; }
            .top { text-align: center; margin-bottom: 30px; }
            .top a {
                background: #1677ff;
                color: white;
                padding: 12px 18px;
                border-radius: 10px;
                text-decoration: none;
                margin: 6px;
            }
            .gallery {
                display: flex;
                flex-wrap: wrap;
                gap: 20px;
            }
            .card {
                background: white;
                border-radius: 12px;
                overflow: hidden;
                width: 300px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            .card img { width: 100%; }
            .card-content { padding: 15px; }
            .time, .age {
                color: gray;
                font-size: 13px;
            }
            .delete-btn {
                background: #ff4d4f;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 8px;
                cursor: pointer;
                width: 100%;
                margin-top: 10px;
            }
        </style>
    </head>
    <body>
        <h1>宝宝成长相册 👶</h1>
        <div class="top">
            <a href="/">返回首页</a>
            <a href="/upload">上传新照片</a>
            <a href="/timeline">成长时间轴</a>
            <a href="/video">成长视频</a>
        </div>
        <div class="gallery">
    """

    for item in media_list:
        upload_date = item.created_at.date()
        html += f"""
        <div class="card">
            <img src="{item.file_path}" />
            <div class="card-content">
                <h3>{item.note or "宝宝照片"}</h3>
                <p class="time">📅 {upload_date}</p>
                <p class="age">👶 {baby_age_text(upload_date)}</p>

                <form action="/delete-photo/{item.id}" method="post" onsubmit="return confirm('确定删除这张照片吗？');">
                    <button class="delete-btn" type="submit">删除这张照片</button>
                </form>
            </div>
        </div>
        """

    html += """
        </div>
    </body>
    </html>
    """

    return html