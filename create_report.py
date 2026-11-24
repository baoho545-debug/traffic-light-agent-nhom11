from pathlib import Path
import csv
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT=Path(__file__).resolve().parent
DATA=ROOT/"ket_qua"/"bang_so_sanh.csv"
OUT=ROOT/"Bao_cao_Tac_tu_den_giao_thong.docx"
with DATA.open(encoding="utf-8-sig",newline="") as f: rows=list(csv.DictReader(f))
doc=Document()
sec=doc.sections[0]; sec.top_margin=Inches(.7); sec.bottom_margin=Inches(.7)
sec.left_margin=Inches(.8); sec.right_margin=Inches(.8)
doc.styles["Normal"].font.name="Arial"; doc.styles["Normal"].font.size=Pt(11)
for name in ("Title","Heading 1","Heading 2"):
    doc.styles[name].font.name="Arial"
def p(t): doc.add_paragraph(t)
doc.add_heading("BÁO CÁO BÀI TẬP LỚN",0)
doc.add_heading("Tác tử điều khiển đèn tín hiệu giao thông thông minh",1)
p("Mô phỏng Poisson; so sánh điều khiển cố định và phản xạ theo mật độ.")
doc.add_heading("1. Mục tiêu và phạm vi",1)
p("Xây dựng mô phỏng giao lộ hai trục Bắc–Nam và Đông–Tây. Xe đến theo phân phối Poisson. So sánh bộ điều khiển chu kỳ cố định với tác tử dựa trên hàng đợi và ước lượng lưu lượng. Mô hình chưa đại diện đầy đủ cho giao thông thực tế.")
doc.add_heading("2. Thuật toán",1)
p("Tác tử cập nhật tốc độ xe đến bằng EWMA, tính áp lực bằng số xe đang chờ cộng lượng xe dự kiến trong 20 giây tiếp theo. Tác tử chỉ chuyển pha sau tối thiểu 25 giây xanh, chuyển nếu hướng kia có áp lực lớn hơn 5 xe hoặc hướng hiện tại hết xe trong khi hướng kia có xe; xanh tối đa 60 giây.")
doc.add_heading("3. Thiết lập thực nghiệm",1)
p("Mỗi lượt mô phỏng kéo dài 3.600 giây; 20 lần lặp cho mỗi mức lưu lượng. Hai phương pháp nhận cùng luồng xe trong từng lần lặp. Tốc độ phục vụ là 0,5 xe/giây; vàng 3 giây; toàn đỏ 1 giây.")
doc.add_heading("4. Kết quả",1)
table=doc.add_table(rows=1,cols=4); table.style="Table Grid"; table.alignment=WD_TABLE_ALIGNMENT.CENTER
for c,t in zip(table.rows[0].cells,["Mức","Cố định (s)","Phản xạ (s)","Giảm (%)"]): c.text=t
for sc in ("Thap","Trung binh","Cao"):
    f=next(r for r in rows if r["scenario"]==sc and r["strategy"]=="Co dinh")
    a=next(r for r in rows if r["scenario"]==sc and r["strategy"]=="Phan xa theo mat do")
    cells=table.add_row().cells
    for c,t in zip(cells,[sc,f'{float(f["average_wait_seconds"]):.2f}',f'{float(a["average_wait_seconds"]):.2f}',f'{float(a["wait_reduction_percent"]):.2f}%']): c.text=t
for image in ["bieu_do_so_sanh.png","bieu_do_ty_le_cai_thien.png"]:
    path=ROOT/"ket_qua"/image
    if path.exists(): doc.add_picture(str(path),width=Inches(5.8))
doc.add_heading("5. Kết luận và giới hạn",1)
p("Trong bộ tham số hiện tại, tác tử thích nghi giảm thời gian chờ ở ba mức lưu lượng. Đây là kết quả mô phỏng; cần thử thêm nhiều tham số, dữ liệu thực và SUMO trước khi kết luận cho giao thông thực tế.")
doc.add_heading("Tài liệu tham khảo",1)
for t in ["Python Documentation: https://docs.python.org/3/","Pygame Documentation: https://www.pygame.org/docs/","Eclipse SUMO Documentation: https://sumo.dlr.de/docs/"]: doc.add_paragraph(t,style="List Bullet")
doc.save(OUT); print("Da tao:",OUT)
