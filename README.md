# SMART TRAFFIC LIGHT AGENT – PROJECT PYTHON

## Chức năng
- Mô phỏng xe đến theo phân phối Poisson.
- So sánh điều khiển đèn cố định với tác tử phản xạ dựa trên mô hình.
- Thử nghiệm 3 mức lưu lượng: thấp, trung bình, cao.
- Chạy giao diện trực quan bằng Pygame.
- Xuất dữ liệu CSV, biểu đồ PNG và báo cáo Word.

## Cài đặt
Mở Terminal tại thư mục project:
```bash
python -m pip install -r requirements.txt
```

## Chạy mô phỏng thực nghiệm
```bash
python main.py
```
Kết quả nằm trong thư mục `ket_qua`.

## Chạy giao diện Pygame
```bash
python pygame_gui.py
```

### Phím điều khiển
- `1`: lưu lượng thấp
- `2`: lưu lượng trung bình
- `3`: lưu lượng cao
- `F`: chiến lược đèn cố định
- `A`: tác tử thích nghi theo mật độ
- `SPACE`: tạm dừng / tiếp tục
- `R`: đặt lại mô phỏng
- `+` / `-`: tăng / giảm tốc độ
- `ESC`: thoát

## Tạo lại báo cáo Word
```bash
python create_report.py
```

## Mô hình và giới hạn
Đây là mô hình học tập tại giao lộ hai trục (Bắc–Nam và Đông–Tây). Xe đến theo phân phối Poisson. Tác tử cập nhật ước lượng lưu lượng bằng EWMA, tính áp lực từ hàng đợi hiện tại và lượng xe dự kiến trong khoảng dự báo, đồng thời áp dụng thời gian xanh tối thiểu/tối đa và pha vàng/toàn đỏ.

Mô phỏng chưa bao gồm rẽ trái/rẽ phải, người đi bộ, ưu tiên xe cứu thương, làn rẽ riêng, cảm biến vật lý hoặc mạng lưới nhiều nút giao. Không sử dụng để điều khiển hệ thống đèn giao thông thật.
