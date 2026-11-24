import math
import random
from collections import deque
from dataclasses import dataclass

import pygame
from main import SimulationConfig, FixedTimeController, ModelBasedAdaptiveController, poisson_sample

WIDTH, HEIGHT = 1100, 760
FPS = 60
CONFIG = SimulationConfig()
SCENARIOS = {"Thap": (0.06, 0.06), "Trung binh": (0.14, 0.14), "Cao": (0.22, 0.22)}

BG = (31, 42, 48)
ROAD = (65, 70, 75)
ROAD_LINE = (230, 210, 120)
WHITE = (245, 245, 245)
RED = (225, 65, 65)
YELLOW = (245, 190, 55)
GREEN = (45, 190, 95)
DARK = (20, 25, 30)
LANE = (190, 195, 198)
CAR_GAP = 52
APPROACH_DISTANCE = 125

@dataclass
class Car:
    direction: str
    created: float
    color: tuple
    route: str = "THANG"
    distance: float = 0.0
    leaving: bool = False
    exit_progress: float = 0.0

class TrafficGUI:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Smart Traffic Light Agent - Mo phong giao thong")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("segoeui", 20)
        self.small = pygame.font.SysFont("segoeui", 15)
        self.big = pygame.font.SysFont("segoeui", 27, bold=True)
        self.running = True
        self.paused = False
        self.speed = 1.0
        self.scenario_name = "Trung binh"
        self.strategy = "Phan xa theo mat do"
        self.reset()

    def reset(self):
        self.sim_time = 0.0
        self.time_accumulator = 0.0
        self.queues = {"NS": deque(), "EW": deque()}
        self.cars = {"N": [], "S": [], "E": [], "W": []}
        self.arrival_rates = SCENARIOS[self.scenario_name]
        self.rng = random.Random(73)
        self.controller = (FixedTimeController(CONFIG) if self.strategy == "Co dinh"
                           else ModelBasedAdaptiveController(CONFIG))
        self.credit = {"NS": 0.0, "EW": 0.0}
        self.total_arrivals = 0
        self.served = 0
        self.total_wait = 0.0
        self.spawn_colors = [(70,170,245),(245,150,65),(160,120,220),(70,190,160),(230,100,130)]

    def axis_queue(self, axis):
        return len(self.queues[axis])

    def spawn(self, direction, count):
        axis = "NS" if direction in ("N", "S") else "EW"
        for _ in range(count):
            route = self.rng.choices(("RE TRAI", "THANG", "RE PHAI"), weights=(0.25, 0.50, 0.25))[0]
            self.cars[direction].append(Car(direction, self.sim_time, self.rng.choice(self.spawn_colors), route))
            self.queues[axis].append(self.sim_time)
            self.total_arrivals += 1

    def _serve_one(self, axis):
        directions = ("N", "S") if axis == "NS" else ("E", "W")
        candidates = []
        for d in directions:
            for car in self.cars[d]:
                if not car.leaving and car.distance >= 0.985:
                    candidates.append((car.created, d, car))
        if not candidates:
            return False
        _, _, car = min(candidates, key=lambda item: item[0])
        car.leaving = True
        car.exit_progress = 0.0
        if self.queues[axis]:
            self.queues[axis].popleft()
        self.total_wait += max(0.0, self.sim_time - car.created)
        self.served += 1
        return True

    def step_second(self):
        rates = self.arrival_rates
        arrivals_ns = poisson_sample(rates[0], self.rng)
        arrivals_ew = poisson_sample(rates[1], self.rng)
        n_ns = arrivals_ns // 2
        m_ns = arrivals_ns - n_ns
        if arrivals_ns % 2 and self.rng.random() < 0.5:
            n_ns, m_ns = m_ns, n_ns
        self.spawn("N", n_ns)
        self.spawn("S", m_ns)
        n_ew = arrivals_ew // 2
        m_ew = arrivals_ew - n_ew
        if arrivals_ew % 2 and self.rng.random() < 0.5:
            n_ew, m_ew = m_ew, n_ew
        self.spawn("E", n_ew)
        self.spawn("W", m_ew)
        self.controller.update_arrival_estimates((arrivals_ns, arrivals_ew))
        if self.controller.mode == "GREEN":
            axis = self.controller.green_direction
            self.credit[axis] += CONFIG.service_rate
            while self.credit[axis] >= 1 and self.queues[axis]:
                if not self._serve_one(axis):
                    self.credit[axis] = min(self.credit[axis], 1.0)
                    break
                self.credit[axis] -= 1
        self.controller.advance(self.queues, (arrivals_ns, arrivals_ew))

    def update(self, dt):
        if self.paused:
            return
        sim_dt = dt * self.speed
        self.time_accumulator += sim_dt
        while self.time_accumulator >= 1.0:
            self.step_second()
            self.time_accumulator -= 1.0
            self.sim_time += 1.0
        # One movement update per frame; speed is applied only once.
        for d in self.cars:
            for car in self.cars[d]:
                if car.leaving:
                    car.exit_progress = min(1.0, car.exit_progress + sim_dt * 0.42)
                else:
                    car.distance = min(1.0, car.distance + sim_dt * 0.70)
            self.cars[d] = [c for c in self.cars[d] if not (c.leaving and c.exit_progress >= 1.0)]

    def draw_text(self, text, x, y, font=None, color=WHITE):
        self.screen.blit((font or self.font).render(str(text), True, color), (int(x), int(y)))

    @staticmethod
    def dashed_line(surface, color, start, end, width=2, dash=18, gap=13):
        x1, y1 = start
        x2, y2 = end
        length = math.hypot(x2-x1, y2-y1)
        if length == 0:
            return
        dx, dy = (x2-x1)/length, (y2-y1)/length
        pos = 0.0
        while pos < length:
            finish = min(pos + dash, length)
            pygame.draw.line(surface, color,
                             (int(x1+dx*pos), int(y1+dy*pos)),
                             (int(x1+dx*finish), int(y1+dy*finish)), width)
            pos += dash + gap

    def draw_arrow(self, x, y, direction, color=(220,220,220), scale=1.0):
        # Simple lane arrow: straight, left-turn or right-turn.
        s = scale
        if direction == "S":
            pts = [(x, y-13*s), (x-8*s, y-3*s), (x-3*s, y-3*s),
                   (x-3*s, y+13*s), (x+3*s, y+13*s), (x+3*s, y-3*s),
                   (x+8*s, y-3*s)]
        elif direction == "L":
            pts = [(x-13*s,y), (x-3*s,y-8*s), (x-3*s,y-3*s),
                   (x+13*s,y-3*s), (x+13*s,y+3*s), (x-3*s,y+3*s), (x-3*s,y+8*s)]
        else:
            pts = [(x+13*s,y), (x+3*s,y-8*s), (x+3*s,y-3*s),
                   (x-13*s,y-3*s), (x-13*s,y+3*s), (x+3*s,y+3*s), (x+3*s,y+8*s)]
        pygame.draw.polygon(self.screen, color, pts)

    def draw_tree(self, x, y):
        # Cum cay nho tren via he de giao dien co cam giac giong ban do giao thong.
        pygame.draw.circle(self.screen, (22, 48, 39), (x+2, y+3), 13)
        pygame.draw.circle(self.screen, (38, 91, 59), (x, y), 12)
        pygame.draw.circle(self.screen, (56, 117, 70), (x-4, y-4), 6)

    def draw_zebra(self, rect, vertical=False):
        x, y, w, h = rect
        if vertical:
            for yy in range(y, y+h, 15):
                pygame.draw.rect(self.screen, (225, 228, 222), (x, yy, w, 8))
        else:
            for xx in range(x, x+w, 17):
                pygame.draw.rect(self.screen, (225, 228, 222), (xx, y, 9, h))

    def draw_road(self):
        # Nen via he, mat duong va giao lo theo phong cach ban do giao thong truc quan.
        self.screen.fill((42, 69, 54))
        pygame.draw.rect(self.screen, (66, 83, 70), (0, 0, WIDTH, HEIGHT))
        # Via he / le duong quanh giao lo.
        pygame.draw.rect(self.screen, (113, 119, 112), (0, 238, WIDTH, 274))
        pygame.draw.rect(self.screen, (113, 119, 112), (414, 0, 272, HEIGHT))
        pygame.draw.rect(self.screen, (74, 79, 78), (0, 250, WIDTH, 250))
        pygame.draw.rect(self.screen, (74, 79, 78), (426, 0, 248, HEIGHT))
        # Vien le duong.
        pygame.draw.rect(self.screen, (205, 203, 185), (0, 246, WIDTH, 4))
        pygame.draw.rect(self.screen, (205, 203, 185), (0, 500, WIDTH, 4))
        pygame.draw.rect(self.screen, (205, 203, 185), (422, 0, 4, HEIGHT))
        pygame.draw.rect(self.screen, (205, 203, 185), (674, 0, 4, HEIGHT))
        # Nen mat duong co lop bong nhe.
        pygame.draw.rect(self.screen, (59, 64, 68), (0, 260, WIDTH, 230))
        pygame.draw.rect(self.screen, (59, 64, 68), (438, 0, 224, HEIGHT))
        # Via he co cay xanh, tranh vung xe chay.
        for p in [(45,55),(120,190),(1010,65),(1060,190),(55,570),(155,700),(960,570),(1040,700)]:
            self.draw_tree(*p)
        # Vach phan cach lan: ba lan rieng cho moi huong vao nut giao.
        for x in (470, 510, 550, 590, 630):
            self.dashed_line(self.screen, (218, 218, 204), (x, 0), (x, 235), 2, 17, 14)
            self.dashed_line(self.screen, (218, 218, 204), (x, 505), (x, HEIGHT), 2, 17, 14)
        for y in (300, 340, 380, 420, 460):
            self.dashed_line(self.screen, (218, 218, 204), (0, y), (410, y), 2, 17, 14)
            self.dashed_line(self.screen, (218, 218, 204), (690, y), (WIDTH, y), 2, 17, 14)
        # Vach dung va vach qua duong.
        pygame.draw.line(self.screen, (245,245,238), (438,238), (662,238), 5)
        pygame.draw.line(self.screen, (245,245,238), (438,512), (662,512), 5)
        pygame.draw.line(self.screen, (245,245,238), (412,260), (412,490), 5)
        pygame.draw.line(self.screen, (245,245,238), (688,260), (688,490), 5)
        self.draw_zebra((440, 242, 220, 14), False)
        self.draw_zebra((440, 494, 220, 14), False)
        self.draw_zebra((414, 270, 14, 210), True)
        self.draw_zebra((672, 270, 14, 210), True)
        # O giao lo va vung trung tam.
        pygame.draw.rect(self.screen, (67, 72, 75), (426, 250, 248, 250))
        pygame.draw.rect(self.screen, (105, 110, 111), (426, 250, 248, 250), 2)
        # Mui ten dat dung tam tung lan va dung theo huong xe tiep can nut giao.
        # Bac di xuong: trai -> phai man hinh, thang -> xuong, phai -> trai.
        self.draw_lane_markings("N", ((450, "→"), (490, "↓"), (530, "←")), 205)
        # Nam di len: trai -> trai man hinh, thang -> len, phai -> phai.
        self.draw_lane_markings("S", ((650, "←"), (610, "↑"), (570, "→")), 555)
        # Tay di sang phai: re trai len tren, thang sang phai, re phai xuong duoi.
        self.draw_lane_markings("W", ((300, "↑"), (340, "→"), (380, "↓")), 365)
        # Dong di sang trai: re trai xuong duoi, thang sang trai, re phai len tren.
        self.draw_lane_markings("E", ((480, "↓"), (440, "←"), (400, "↑")), 735)
        # Ten huong dat tren via he, de nguoi xem nhan biet ngay.
        self.draw_tag("HƯỚNG BẮC", 474, 8, (26, 76, 133))
        self.draw_tag("HƯỚNG NAM", 474, 710, (26, 76, 133))
        self.draw_tag("HƯỚNG TÂY", 8, 390, (26, 76, 133), vertical=True)
        self.draw_tag("HƯỚNG ĐÔNG", 1048, 390, (26, 76, 133), vertical=True)

    def draw_lane_markings(self, approach, entries, fixed):
        """Ve mui ten theo chieu chay thuc te cua tung nhanh duong."""
        for lane_position, glyph in entries:
            surf = self.big.render(glyph, True, (238, 239, 230))
            if approach in ("N", "S"):
                rect = surf.get_rect(center=(lane_position, fixed))
            else:
                rect = surf.get_rect(center=(fixed, lane_position))
            self.screen.blit(surf, rect)

    def draw_tag(self, text, x, y, color, vertical=False):
        font = self.small
        surf = font.render(text, True, WHITE)
        if vertical:
            surf = pygame.transform.rotate(surf, 90)
        rect = surf.get_rect(center=(x + (surf.get_width()//2 if not vertical else 18), y + (surf.get_height()//2 if not vertical else 48)))
        pygame.draw.rect(self.screen, color, rect.inflate(16, 10), border_radius=8)
        pygame.draw.rect(self.screen, (155,190,215), rect.inflate(16, 10), 1, border_radius=8)
        self.screen.blit(surf, rect)

    def lane_center(self, direction, route):
        lane = {"RE TRAI": 0, "THANG": 1, "RE PHAI": 2}[route]
        centers = {
            "N": (450, 490, 530),
            "S": (650, 610, 570),
            "W": (280, 320, 360),
            "E": (480, 440, 400),
        }
        return centers[direction][lane]

    def route_points(self, direction, route, start_lane):
        # Cubic Bezier paths connect each dedicated incoming lane to its exit.
        if direction == "N":
            sx = start_lane
            paths = {
                "THANG": ((sx,245),(sx,330),(sx,430),(sx,535)),
                "RE TRAI": ((sx,245),(sx,315),(700,325),(760,325)),
                "RE PHAI": ((sx,245),(sx,300),(390,420),(350,435)),
            }
        elif direction == "S":
            sx = start_lane
            paths = {
                "THANG": ((sx,515),(sx,430),(sx,330),(sx,220)),
                "RE TRAI": ((sx,515),(sx,435),(390,435),(350,435)),
                "RE PHAI": ((sx,515),(sx,440),(700,325),(760,325)),
            }
        elif direction == "W":
            sy = start_lane
            paths = {
                "THANG": ((415,sy),(500,sy),(600,sy),(700,sy)),
                "RE TRAI": ((415,sy),(500,sy),(595,220),(595,175)),
                "RE PHAI": ((415,sy),(500,sy),(505,535),(505,590)),
            }
        else:  # E
            sy = start_lane
            paths = {
                "THANG": ((685,sy),(600,sy),(500,sy),(400,sy)),
                "RE TRAI": ((685,sy),(600,sy),(505,535),(505,590)),
                "RE PHAI": ((685,sy),(600,sy),(595,220),(595,175)),
            }
        return paths[route]

    @staticmethod
    def bezier(points, t):
        p0, p1, p2, p3 = points
        u = 1.0 - t
        x = u**3*p0[0] + 3*u*u*t*p1[0] + 3*u*t*t*p2[0] + t**3*p3[0]
        y = u**3*p0[1] + 3*u*u*t*p1[1] + 3*u*t*t*p2[1] + t**3*p3[1]
        return x, y

    def draw_vehicle(self, car, x, y, direction, angle=0):
        vertical = direction in ("N", "S")
        w, h = (25, 40) if vertical else (40, 25)
        body = pygame.Surface((w+8, h+8), pygame.SRCALPHA)
        pygame.draw.rect(body, (12, 15, 18), (1, 1, w+6, h+6), border_radius=7)
        pygame.draw.rect(body, car.color, (4, 4, w, h), border_radius=6)
        if vertical:
            pygame.draw.rect(body, (185, 220, 235), (8, 10, 17, 10), border_radius=3)
            pygame.draw.rect(body, (185, 220, 235), (8, 25, 17, 8), border_radius=2)
            pygame.draw.circle(body, (255,245,190), (9, 6), 2)
            pygame.draw.circle(body, (255,245,190), (23, 6), 2)
        else:
            pygame.draw.rect(body, (185, 220, 235), (10, 8, 10, 17), border_radius=3)
            pygame.draw.rect(body, (185, 220, 235), (25, 8, 8, 17), border_radius=2)
            pygame.draw.circle(body, (255,245,190), (6, 9), 2)
            pygame.draw.circle(body, (255,245,190), (6, 23), 2)
        rotated = pygame.transform.rotate(body, angle)
        self.screen.blit(rotated, rotated.get_rect(center=(int(x), int(y))))

    def draw_cars(self):
        for direction, cars in self.cars.items():
            lane_indices = {"RE TRAI": 0, "THANG": 0, "RE PHAI": 0}
            for car in sorted(cars, key=lambda c: c.created):
                if car.leaving:
                    lane = self.lane_center(direction, car.route)
                    pts = self.route_points(direction, car.route, lane)
                    x, y = self.bezier(pts, car.exit_progress)
                    ahead = min(1.0, car.exit_progress + 0.015)
                    x2, y2 = self.bezier(pts, ahead)
                    angle = -math.degrees(math.atan2(y2-y, x2-x))
                    self.draw_vehicle(car, x, y, direction, angle)
                    continue
                index = lane_indices[car.route]
                lane_indices[car.route] += 1
                lane = self.lane_center(direction, car.route)
                offset = (1.0-car.distance) * APPROACH_DISTANCE + index * CAR_GAP
                if direction == "N":
                    x, y = lane, 245 - 22 - offset
                elif direction == "S":
                    x, y = lane, 515 + 22 + offset
                elif direction == "W":
                    x, y = 415 - 22 - offset, lane
                else:
                    x, y = 685 + 22 + offset, lane
                self.draw_vehicle(car, x, y, direction)

    def draw_signal(self, x, y, axis, label, tag_x, tag_y):
        """Den doc dat tren via he tai dau nhanh duong no dieu khien."""
        is_green = self.controller.mode == "GREEN" and self.controller.green_direction == axis
        is_yellow = self.controller.mode == "YELLOW" and self.controller.green_direction == axis
        active = GREEN if is_green else (YELLOW if is_yellow else RED)
        rect = pygame.Rect(x, y, 40, 88)
        pygame.draw.rect(self.screen, (7, 12, 16), rect.inflate(6, 6), border_radius=10)
        pygame.draw.rect(self.screen, (19, 27, 31), rect, border_radius=9)
        for i, color in enumerate((RED, YELLOW, GREEN)):
            pygame.draw.circle(self.screen, color if color == active else (55, 61, 63),
                               (x + 20, y + 17 + i * 27), 9)
        # Dat nhan tach khoi den, tranh de len xe, mui ten va bang thong ke.
        self.draw_tag(label, tag_x, tag_y, (18, 45, 58))

    def draw_dashboard(self):
        pygame.draw.rect(self.screen, (12, 22, 28), (14, 14, 345, 205), border_radius=16)
        pygame.draw.rect(self.screen, (72, 111, 130), (14, 14, 345, 205), 1, border_radius=16)
        self.draw_text("SMART TRAFFIC LIGHT AGENT", 28, 26, self.big)
        self.draw_text(f"Thời gian mô phỏng: {self.sim_time:,.1f} s", 29, 69, self.small)
        self.draw_text(f"Chiến lược: {self.strategy}", 29, 96, self.small)
        self.draw_text(f"Lưu lượng: {self.scenario_name}", 29, 123, self.small)
        self.draw_text(f"Hàng chờ Bắc-Nam: {len(self.queues['NS'])} xe", 29, 150, self.small)
        self.draw_text(f"Hàng chờ Đông-Tây: {len(self.queues['EW'])} xe", 29, 177, self.small)
        pygame.draw.rect(self.screen, (12, 22, 28), (755, 14, 330, 205), border_radius=16)
        pygame.draw.rect(self.screen, (72, 111, 130), (755, 14, 330, 205), 1, border_radius=16)
        self.draw_text("THỐNG KÊ", 775, 26, self.big)
        avg = self.total_wait / self.served if self.served else 0
        self.draw_text(f"Tổng xe đến: {self.total_arrivals}", 775, 69, self.small)
        self.draw_text(f"Xe đã qua: {self.served}", 775, 96, self.small)
        self.draw_text(f"Xe đang chờ: {sum(map(len,self.queues.values()))}", 775, 123, self.small)
        self.draw_text(f"Chờ TB xe đã phục vụ: {avg:.1f} s", 775, 150, self.small)
        phase = self.controller.mode
        self.draw_text(f"Trạng thái đèn: {phase}", 775, 177, self.small, GREEN if phase == "GREEN" else YELLOW if phase == "YELLOW" else RED)

    def draw_controls(self):
        pygame.draw.rect(self.screen, (12, 22, 28), (14, 635, 1072, 111), border_radius=16)
        pygame.draw.rect(self.screen, (72, 111, 130), (14, 635, 1072, 111), 1, border_radius=16)
        lines = [
            "PHÍM ĐIỀU KHIỂN: [1] Lưu lượng thấp   [2] Trung bình   [3] Cao",
            "[F] Đèn cố định   [A] Đèn thích nghi   [SPACE] Tạm dừng / tiếp tục",
            "[R] Đặt lại mô phỏng   [+/-] Tăng / giảm tốc độ   [ESC] Thoát",
            "Làn xe: ← Rẽ trái     ↑ Đi thẳng     → Rẽ phải     |     Đèn gắn nhãn theo hướng xe đi vào",
            f"Tốc độ mô phỏng: {self.speed:.1f}x   |   Trạng thái: {'TẠM DỪNG' if self.paused else 'ĐANG CHẠY'}"
        ]
        for i, line in enumerate(lines):
            self.draw_text(line, 31, 642+i*19, self.small, YELLOW if i == 0 else WHITE)

    def draw(self):
        self.draw_road()
        self.draw_cars()
        # Moi den nam o goc via he gan vach dung cua huong xe di vao.
        # Bac va Nam cung pha NS; Dong va Tay cung pha EW.
        self.draw_signal(680, 135, "NS", "ĐÈN HƯỚNG BẮC", 620, 102)
        self.draw_signal(365, 520, "NS", "ĐÈN HƯỚNG NAM", 310, 590)
        self.draw_signal(365, 235, "EW", "ĐÈN HƯỚNG TÂY", 370, 205)
        self.draw_signal(690, 520, "EW", "ĐÈN HƯỚNG ĐÔNG", 735, 565)
        self.draw_dashboard()
        self.draw_controls()
        pygame.display.flip()

    def handle(self, event):
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE: self.running = False
            elif event.key == pygame.K_SPACE: self.paused = not self.paused
            elif event.key == pygame.K_r: self.reset()
            elif event.key == pygame.K_1: self.scenario_name = "Thap"; self.reset()
            elif event.key == pygame.K_2: self.scenario_name = "Trung binh"; self.reset()
            elif event.key == pygame.K_3: self.scenario_name = "Cao"; self.reset()
            elif event.key == pygame.K_f: self.strategy = "Co dinh"; self.reset()
            elif event.key == pygame.K_a: self.strategy = "Phan xa theo mat do"; self.reset()
            elif event.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS): self.speed = min(10, self.speed+0.5)
            elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS): self.speed = max(0.5, self.speed-0.5)

    def run(self):
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            for event in pygame.event.get():
                self.handle(event)
            self.update(dt)
            self.draw()
        pygame.quit()

if __name__ == "__main__":
    TrafficGUI().run()
