from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, Column, Integer, String, DateTime, text
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime, date
import os
import uuid
import shutil
import requests
import html as html_lib

from PIL import Image, ImageDraw, ImageFont
from moviepy import ImageClip, concatenate_videoclips

from dotenv import load_dotenv
from qcloud_cos import CosConfig, CosS3Client


load_dotenv()

SECRET_ID = os.getenv("TENCENT_SECRET_ID")
SECRET_KEY = os.getenv("TENCENT_SECRET_KEY")
REGION = os.getenv("TENCENT_REGION")
BUCKET = os.getenv("TENCENT_BUCKET")

config = CosConfig(
    Region=REGION,
    SecretId=SECRET_ID,
    SecretKey=SECRET_KEY
)
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
    diary = Column(String)
    created_at = Column(DateTime, default=datetime.now)


class Milestone(Base):
    __tablename__ = "milestones"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    description = Column(String)
    event_date = Column(String)
    created_at = Column(DateTime, default=datetime.now)


Base.metadata.create_all(bind=engine)


def ensure_diary_column():
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE media ADD COLUMN diary TEXT"))
            conn.commit()
    except Exception:
        pass


ensure_diary_column()


BABY_NAME = "派派"
BABY_BIRTHDAY = date(2026, 2, 13)


def esc(value):
    return html_lib.escape(str(value or ""))


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

    if months <= 0:
        return f"第{days}天"

    month_start_year = BABY_BIRTHDAY.year + (BABY_BIRTHDAY.month + months - 1) // 12
    month_start_month = (BABY_BIRTHDAY.month + months - 1) % 12 + 1
    month_start_day = min(BABY_BIRTHDAY.day, 28)

    month_start = date(month_start_year, month_start_month, month_start_day)
    extra_days = (target_date - month_start).days

    return f"第{days}天（{months}个月{extra_days}天）"


def make_diary(note, created_at):
    upload_date = created_at.date()
    age = baby_age_text(upload_date)
    note_text = note.strip() if note else "今天记录下了派派成长中的一个小瞬间。"

    if "抓" in note_text or "握" in note_text or "拿" in note_text or "奶瓶" in note_text or "玩具" in note_text:
        detail = """今天派派开始主动伸手去抓东西了。

主动抓握并不是一个简单的小动作，
它代表着手眼协调能力正在一点点发展。

从看到眼前的东西，
到尝试伸手靠近，
再到慢慢握住它，
这中间每一步，
都是派派认识世界的重要过程。"""

    elif "翻身" in note_text:
        detail = """今天派派完成了一个很重要的动作：翻身。

翻身是身体力量、协调能力和探索欲望一起发展的结果。

从只能安静地躺着，
到开始尝试转动身体，
这说明派派正在用自己的方式，
一点点打开更大的世界。"""

    elif "抬头" in note_text:
        detail = """今天派派抬头的表现又进步了。

抬头看起来只是一个小动作，
但它需要颈部、背部和核心力量一起配合。

每一次努力抬起头，
都是派派身体力量慢慢增强的证明。"""

    elif "坐" in note_text or "坐着" in note_text:
        detail = """今天派派在坐这件事上有了新的进步。

能慢慢坐起来，
说明他的腰背力量和平衡能力正在发展。

从被抱着，
到开始尝试自己支撑身体，
这是成长路上很重要的一步。"""

    elif "爬" in note_text:
        detail = """今天派派开始尝试爬了。

爬行是宝宝探索世界的重要阶段，
它需要手臂、腿部、腰背和协调能力一起配合。

从原地努力，
到慢慢向前移动，
每一点进步都很珍贵。"""

    elif "站" in note_text:
        detail = """今天派派开始尝试站起来了。

站立意味着腿部力量和平衡能力正在增强。

虽然现在可能还需要大人扶着，
但这已经是走向更大世界的重要一步。"""

    elif "走" in note_text or "迈步" in note_text:
        detail = """今天派派在走路这件事上有了新的尝试。

每一次迈步，
都是勇气、力量和平衡感的练习。

从被抱着看世界，
到慢慢用自己的脚探索世界，
这一天很值得纪念。"""

    elif "说话" in note_text or "爸爸" in note_text or "妈妈" in note_text or "发声" in note_text:
        detail = """今天派派在声音表达上有了新的变化。

宝宝的每一次发声，
都是他尝试和世界交流的开始。

无论是含糊的小声音，
还是第一次喊出爸爸妈妈，
都是家人心里特别珍贵的瞬间。"""

    elif "笑" in note_text or "微笑" in note_text:
        detail = """今天派派笑了。

宝宝的笑容总是很神奇，
它不只是一个表情，
也是他开始回应家人、感受爱和安全感的方式。

这一刻很普通，
却也特别温柔。"""

    elif "睡" in note_text or "睡觉" in note_text:
        detail = """今天记录下的是派派安静睡觉的样子。

宝宝熟睡的时候，
总让人觉得时间都变慢了。

看着他安安稳稳地睡着，
爸爸妈妈也会觉得这一切辛苦都很值得。"""

    elif "辅食" in note_text or "吃" in note_text:
        detail = """今天派派在吃东西这件事上有了新的体验。

从只会喝奶，
到慢慢接触新的味道和口感，
这是宝宝成长中很重要的一步。

每一次尝试，
都是他认识世界的新方式。"""

    elif "牙" in note_text or "长牙" in note_text:
        detail = """今天记录下了派派长牙相关的小变化。

长牙是宝宝成长中很重要的阶段，
可能会有一点不舒服，
也可能会变得更爱咬东西。

这些小小的变化，
都说明派派正在认真长大。"""

    elif "疫苗" in note_text or "体检" in note_text:
        detail = """今天是派派成长记录里很重要的一天。

体检、疫苗这些事情，
虽然过程可能会有一点不舒服，
但都是为了让派派更健康、更安心地长大。

这也是成长路上值得被认真记下的一部分。"""

    elif "生病" in note_text or "发烧" in note_text or "咳嗽" in note_text or "感冒" in note_text:
        detail = """今天派派身体有些不舒服。

宝宝生病的时候，
爸爸妈妈会特别心疼，
也会更加认真地照顾和陪伴他。

这一页记录的不只是病痛，
也是家人一起守护派派健康长大的过程。"""

    elif "洗澡" in note_text:
        detail = """今天记录下了派派洗澡的样子。

洗澡对宝宝来说，
不只是清洁身体，
也是一次感受水、感受触摸、感受安全感的小体验。

看着派派慢慢适应水里的感觉，
也是成长中很可爱的一部分。"""

    elif "游泳" in note_text:
        detail = """今天派派体验了游泳。

在水里的每一次摆动，
都是身体协调和力量发展的练习。

对小宝宝来说，
这既是一次新鲜体验，
也是成长路上很值得纪念的一天。"""

    elif "出门" in note_text or "散步" in note_text or "晒太阳" in note_text:
        detail = """今天派派出门感受了外面的世界。

阳光、风、声音和周围的人，
对小小的派派来说，
都是新鲜又特别的体验。

每一次出门，
都是他慢慢认识世界的一小步。"""

    elif "哭" in note_text or "闹" in note_text:
        detail = """今天派派也有一些小情绪。

宝宝哭闹并不只是麻烦，
很多时候也是他表达需求、感受和不舒服的方式。

爸爸妈妈认真记录这些瞬间，
也是在记录派派一点点学会表达自己的过程。"""

    elif "满月" in note_text:
        detail = """今天是派派满月的重要日子。

从出生到满月，
这短短一个月里，
派派每天都在悄悄变化。

这不仅是宝宝成长的第一个小节点，
也是一家人共同适应新生活的重要纪念。"""

    elif "百天" in note_text or "100天" in note_text:
        detail = """今天是派派百天的重要日子。

一百天听起来不长，
但对宝宝和家人来说，
这是一段充满变化、辛苦和幸福的时光。

从刚出生的小小婴儿，
到现在越来越有反应、越来越有力量，
派派已经在认真长大了。"""

    else:
        detail = """也许这只是生活里很普通的一刻，
但对正在慢慢长大的派派来说，
每一次新的动作、表情和反应，
都是成长路上值得被认真保存的印记。"""

    return f"""📅 {upload_date}

今天的派派已经{age}了。

今天，爸爸妈妈为派派记录下了一个新的成长瞬间：

{note_text}

{detail}

爸爸妈妈把这一刻保存下来，
是想让未来的派派知道：
在他还很小很小的时候，
家人就已经在认真地看见他的每一点变化，
也在用心收藏他成长中的每一个瞬间。

多年以后再回头看，
这张照片、这段文字，
都会成为一家人最温柔、最珍贵的回忆。

愿派派继续健康、快乐、平安地长大。"""


def detect_milestone(note):
    note_text = note.strip() if note else ""

    milestone_keywords = [
        "第一次",
        "翻身",
        "抬头",
        "坐",
        "爬",
        "站",
        "走",
        "迈步",
        "说话",
        "爸爸",
        "妈妈",
        "长牙",
        "满月",
        "百天",
        "100天",
        "辅食",
        "游泳",
        "洗澡"
    ]

    for keyword in milestone_keywords:
        if keyword in note_text:
            return note_text

    return None


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

    draw.text((80, 40), "守护派派成长记录", fill=(20, 20, 20), font=title_font)
    draw.text((80, 1540), note or "宝宝成长照片", fill=(20, 20, 20), font=text_font)
    draw.text((80, 1620), f"📅 {upload_date}", fill=(90, 90, 90), font=small_font)
    draw.text((80, 1680), f"👶 {age_text}", fill=(90, 90, 90), font=small_font)

    background.save(output_path)


@app.get("/", response_class=HTMLResponse)
def home():
    db = SessionLocal()
    photo_count = db.query(Media).count()
    diary_count = db.query(Media).filter(Media.diary != None).count()
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
                max-width: 780px;
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
            .diary {{
                background: #722ed1;
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
            <div class="stat">成长日记：{diary_count} 篇</div>
            <div class="stat">成长里程碑：{milestone_count} 条</div>
            <div class="stat">最新里程碑：{esc(latest_text)}</div>

            <a href="/upload">上传照片</a>
            <a href="/gallery">查看相册</a>
            <a href="/timeline">成长时间轴</a>
            <a class="diary" href="/diary">成长日记</a>
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
        <title>上传照片</title>
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
            button:disabled {
                background: gray;
            }
            a {
                display: block;
                text-align: center;
                margin-top: 20px;
            }
        </style>
    </head>
    <body>
        <div class="box">
            <h1>上传照片 👶</h1>

            <form id="uploadForm" action="/upload-photo" method="post" enctype="multipart/form-data">
                <input type="hidden" name="baby_id" value="1">

                <label>照片备注</label>
                <textarea name="note" placeholder="例如：第一次翻身、今天第一次主动抓玩具"></textarea>

                <label>选择照片</label>
                <input type="file" name="file" accept="image/*" required>

                <button id="uploadBtn" type="submit">上传并生成成长日记</button>
            </form>

            <a href="/">返回首页</a>
            <a href="/gallery">查看相册</a>
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

    now = datetime.now()
    diary = make_diary(note, now)

    media = Media(
        baby_id=baby_id,
        media_type="photo",
        file_path=cos_url,
        note=note,
        diary=diary,
        created_at=now
    )

    db.add(media)

    milestone_title = detect_milestone(note)

    if milestone_title:
        milestone = Milestone(
            event_date=str(now.date()),
            title=milestone_title,
            description=f"系统根据照片备注自动记录：{milestone_title}"
        )
        db.add(milestone)

    db.commit()
    db.close()

    milestone_html = ""

    if milestone_title:
        milestone_html = f"""
        <div class="milestone">
            🎉 已自动加入成长时间轴：{esc(milestone_title)}
        </div>
        """

    return HTMLResponse(f"""
    <html>
    <head>
        <title>上传成功</title>
        <style>
            body {{
                font-family: Arial;
                background: #f6f6f6;
                padding: 40px;
            }}
            .box {{
                max-width: 650px;
                margin: auto;
                background: white;
                padding: 30px;
                border-radius: 18px;
                box-shadow: 0 4px 14px rgba(0,0,0,0.12);
            }}
            .diary {{
                white-space: pre-wrap;
                line-height: 1.8;
                background: #fafafa;
                padding: 18px;
                border-radius: 12px;
            }}
            .milestone {{
                margin-top: 18px;
                padding: 14px;
                background: #fff7e6;
                border-radius: 10px;
                font-size: 18px;
            }}
            a {{
                display: block;
                margin-top: 18px;
                text-align: center;
                font-size: 18px;
            }}
        </style>
    </head>
    <body>
        <div class="box">
            <h1>上传成功 🎉</h1>
            <div class="diary">{esc(diary)}</div>
            {milestone_html}
            <a href="/diary">查看成长日记</a>
            <a href="/timeline">查看成长时间轴</a>
            <a href="/gallery">查看相册</a>
            <a href="/upload">继续上传</a>
            <a href="/">返回首页</a>
        </div>
    </body>
    </html>
    """)


@app.get("/diary", response_class=HTMLResponse)
def diary_page():
    db = SessionLocal()
    media_list = db.query(Media).order_by(Media.created_at.desc()).all()
    db.close()

    html = """
    <html>
    <head>
        <title>成长日记</title>
        <style>
            body {
                font-family: Arial;
                background: #f5f5f5;
                padding: 30px;
            }
            h1 {
                text-align: center;
            }
            .top {
                text-align: center;
                margin-bottom: 30px;
            }
            .top a {
                background: #1677ff;
                color: white;
                padding: 12px 18px;
                border-radius: 10px;
                text-decoration: none;
                margin: 6px;
                display: inline-block;
            }
            .card {
                max-width: 760px;
                margin: 0 auto 24px auto;
                background: white;
                border-radius: 16px;
                padding: 22px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.08);
            }
            img {
                width: 180px;
                border-radius: 12px;
                margin-bottom: 12px;
            }
            .text {
                white-space: pre-wrap;
                line-height: 1.8;
                font-size: 17px;
            }
        </style>
    </head>
    <body>
        <h1>派派成长日记 📖</h1>

        <div class="top">
            <a href="/">返回首页</a>
            <a href="/upload">上传照片</a>
            <a href="/gallery">查看相册</a>
        </div>
    """

    if not media_list:
        html += """
        <div class="card">
            <h2>还没有成长日记</h2>
            <p>上传一张照片后，系统会自动生成成长日记。</p>
        </div>
        """

    for item in media_list:
        diary = item.diary or make_diary(item.note, item.created_at)

        html += f"""
        <div class="card">
            <img src="{esc(item.file_path)}" />
            <div class="text">{esc(diary)}</div>
        </div>
        """

    html += """
    </body>
    </html>
    """

    return html


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
            .content { padding: 15px; }
            .time, .age { color: gray; font-size: 13px; }
            .diary {
                background: #fafafa;
                padding: 10px;
                border-radius: 8px;
                white-space: pre-wrap;
                font-size: 13px;
                line-height: 1.5;
                margin-top: 10px;
            }
            .delete {
                background: #ff4d4f;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 8px;
                width: 100%;
                margin-top: 10px;
                cursor: pointer;
            }
        </style>
    </head>
    <body>
        <h1>宝宝成长相册 👶</h1>
        <div class="top">
            <a href="/">返回首页</a>
            <a href="/upload">上传照片</a>
            <a href="/diary">成长日记</a>
            <a href="/timeline">成长时间轴</a>
            <a href="/video">成长视频</a>
        </div>
        <div class="gallery">
    """

    for item in media_list:
        upload_date = item.created_at.date()
        diary = item.diary or make_diary(item.note, item.created_at)

        html += f"""
        <div class="card">
            <img src="{esc(item.file_path)}" />
            <div class="content">
                <h3>{esc(item.note or "宝宝照片")}</h3>
                <p class="time">📅 {upload_date}</p>
                <p class="age">👶 {baby_age_text(upload_date)}</p>
                <div class="diary">{esc(diary)}</div>

                <form action="/delete-photo/{item.id}" method="post" onsubmit="return confirm('确定删除这张照片吗？');">
                    <button class="delete" type="submit">删除这张照片</button>
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


@app.get("/timeline", response_class=HTMLResponse)
def timeline():
    db = SessionLocal()
    milestones = db.query(Milestone).order_by(Milestone.event_date.asc()).all()
    db.close()

    html = """
    <html>
    <head>
        <title>成长时间轴</title>
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
            }
            .item {
                background: white;
                max-width: 700px;
                margin: 0 auto 18px auto;
                padding: 18px;
                border-radius: 14px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.08);
            }
            .delete {
                background: #ff4d4f;
            }
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
                <textarea name="description" placeholder="例如：今天派派自己翻身成功了"></textarea>

                <button type="submit">添加里程碑</button>
            </form>
        </div>
    """

    for item in milestones:
        html += f"""
        <div class="item">
            <p>📅 {esc(item.event_date)}</p>
            <p>👶 {baby_age_text(item.event_date)}</p>
            <h2>{esc(item.title)}</h2>
            <p>{esc(item.description or "")}</p>

            <form action="/delete-milestone/{item.id}" method="post" onsubmit="return confirm('确定删除这条里程碑吗？');">
                <button class="delete" type="submit">删除</button>
            </form>
        </div>
        """

    html += """
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