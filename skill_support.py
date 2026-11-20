"""Installation prompts for the local AI skill guide."""
REPOSITORY = 'https://github.com/phawitb/th-voice-lab.git'


def skill_guide(project=None):
    prompts = {}
    for target, label in [('codex', 'Codex'), ('claude', 'Claude Code')]:
        prompts[target] = (
            f'ติดตั้ง Thai Voice Lab และสกิลสำหรับ {label} บนเครื่องของฉันจาก {REPOSITORY}\n'
            'อ่าน README.md ในรีโปก่อน ตรวจว่ามี Python 3.11–3.13, Git และ ffmpeg ถ้ายังไม่มีให้ช่วยติดตั้งตามระบบของเครื่อง\n'
            f'เลือกโฟลเดอร์ใหม่ที่ไม่ทับงานเดิม แล้วใช้ git clone {REPOSITORY} ถ้ามี checkout นี้อยู่แล้วให้ตรวจสอบและใช้ของเดิม\n'
            f'เข้าโฟลเดอร์ th-voice-lab แล้วรัน python3 scripts/setup.py --target {target} --download-model\n'
            'ตัวติดตั้งจะสร้างสภาพแวดล้อมแยก โหลด VoxCPM2 ครั้งแรก (หลาย GB) และติดตั้งสกิล ใช้ไฟล์ที่มีอยู่แล้วเมื่อทำได้\n'
            'จากนั้นเปิดเซิร์ฟเวอร์ด้วย python3 scripts/start_server.py ตรวจ status และเสียงตัวอย่าง 8 เสียง '
            'ลองสร้างข้อความ “สวัสดี ยินดีต้อนรับสู่ไทยวอยซ์แล็บ” เป็นไฟล์ welcome.wav ที่ไม่ทับไฟล์เดิม '
            'แล้วเปิด http://127.0.0.1:7860 ให้ฉันทดลอง หากพบข้อผิดพลาดให้แก้ตามสาเหตุและรายงานส่วนที่ยังไม่สำเร็จ '
            'ไม่เขียนทับสกิลหรือไฟล์ที่ฉันแก้ไว้ และไม่เปลี่ยนสิทธิ์ของ AI'
        )
    return {
        'name': 'thai-voice-lab', 'repository': REPOSITORY, 'install_prompts': prompts,
        'download_url': '/static/downloads/thai-voice-lab-skill.zip',
        'examples': {
            'codex': 'ใช้ $thai-voice-lab สร้างเสียงจากข้อความ “ยินดีต้อนรับเข้าสู่ thai voice lab สร้างเสียงได้ฟรี ไม่จำกัด บนคอมพิวเตอร์เราเอง” ด้วยเสียงไทย 01 บันทึกเป็น welcome.wav ในโฟลเดอร์งาน แล้วส่งไฟล์ให้ฟัง',
            'claude': '/thai-voice-lab อ่านไฟล์ script.txt ในโฟลเดอร์งาน ด้วยเสียงไทย 02 ความเร็ว 0.95 บันทึกเป็น narration.wav และรอจนสร้างเสร็จ',
            'reference': 'ใช้ skill thai-voice-lab สร้างเสียงจากข้อความใน script.txt โดยใช้ไฟล์ my-voice.wav ที่ฉันมีสิทธิ์ใช้เป็นเสียงอ้างอิง บันทึกเป็น my-narration.wav แล้วส่งไฟล์ให้ฟัง',
        },
    }
