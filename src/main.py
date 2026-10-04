from __future__ import annotations

import asyncio
import json
import random
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import pygame

CELL_SIZE = 24
GRID_WIDTH = 28
GRID_HEIGHT = 22
HEADER_HEIGHT = 72
BOARD_WIDTH = GRID_WIDTH * CELL_SIZE
BOARD_HEIGHT = GRID_HEIGHT * CELL_SIZE
WINDOW_WIDTH = BOARD_WIDTH
WINDOW_HEIGHT = HEADER_HEIGHT + BOARD_HEIGHT
FPS = 60
BASE_MOVE_MS = 145
MIN_MOVE_MS = 70
SPEEDUP_PER_FOOD_MS = 4

# Neon arcade palette
BACKGROUND = (8, 6, 18)
HEADER = (14, 10, 30)
BOARD = (10, 8, 24)
GRID = (26, 20, 52)
SNAKE_HEAD = (170, 255, 120)
SNAKE_BODY = (57, 255, 136)
SNAKE_BODY_ALT = (0, 214, 110)
FOOD = (255, 46, 151)
FOOD_HIGHLIGHT = (255, 160, 214)
TEXT = (240, 238, 255)
MUTED_TEXT = (150, 140, 190)
OVERLAY = (6, 4, 16, 200)
ACCENT = (0, 229, 255)
TITLE = (255, 230, 70)

# Running in the browser (pygbag compiles the game to WebAssembly)
WEB = sys.platform == "emscripten"
SWIPE_MIN_PX = 24
# Turns pressed faster than the snake moves are queued, so a quick "up, left" is never lost
MAX_QUEUED_TURNS = 2
SAVE_PATH = Path.home() / ".snake-best.json"
MODES = ("classic", "wrap")


class Scores:
    """Best score per mode, kept between sessions: a JSON file on desktop, localStorage on the web."""

    KEY = "snake-best"

    def __init__(self, path: Path | None = SAVE_PATH) -> None:
        self.path = path
        self.best = {mode: 0 for mode in MODES}
        try:
            saved = json.loads(self._read() or "{}")
            self.best.update({m: int(v) for m, v in saved.items() if m in MODES})
        except (ValueError, TypeError, OSError):
            pass  # a corrupt or unreadable save just means starting from zero

    def _read(self) -> str | None:
        if WEB:
            import platform  # pygbag's bridge to the browser

            return platform.window.localStorage.getItem(self.KEY)
        if self.path and self.path.exists():
            return self.path.read_text(encoding="utf-8")
        return None

    def record(self, mode: str, score: int) -> bool:
        """Store a score; returns True when it is a new best."""
        if score <= self.best[mode]:
            return False
        self.best[mode] = score
        data = json.dumps(self.best)
        try:
            if WEB:
                import platform

                platform.window.localStorage.setItem(self.KEY, data)
            elif self.path:
                self.path.write_text(data, encoding="utf-8")
        except OSError:
            pass
        return True


class GameState(Enum):
    START = "start"
    PLAYING = "playing"
    PAUSED = "paused"
    GAME_OVER = "game_over"


@dataclass(frozen=True)
class Point:
    x: int
    y: int

    def __add__(self, other: Point) -> Point:
        return Point(self.x + other.x, self.y + other.y)


UP = Point(0, -1)
DOWN = Point(0, 1)
LEFT = Point(-1, 0)
RIGHT = Point(1, 0)


class SnakeGame:
    def __init__(self, scores: Scores | None = None) -> None:
        pygame.init()
        pygame.display.set_caption("Snake")
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 30)
        self.large_font = pygame.font.Font(None, 64)
        self.small_font = pygame.font.Font(None, 24)
        self.state = GameState.START
        self.scores = scores or Scores()
        self.mode = MODES[0]
        self.new_best = False
        self.touch_start: tuple[int, int] | None = None
        self.scanlines = self.make_scanlines()
        self.game_over_title = "GAME OVER"
        self.game_over_subtitle = "Press Space, Enter or tap to restart"
        self.reset()

    def reset(self) -> None:
        center = Point(GRID_WIDTH // 2, GRID_HEIGHT // 2)
        self.snake = [
            center,
            Point(center.x - 1, center.y),
            Point(center.x - 2, center.y),
        ]
        self.direction = RIGHT
        self.turns: list[Point] = []
        self.food = self.spawn_food()
        self.score = 0
        self.new_best = False
        self.move_delay_ms = BASE_MOVE_MS
        self.last_move_ms = pygame.time.get_ticks()
        self.game_over_title = "GAME OVER"
        self.game_over_subtitle = "Press Space, Enter or tap to restart"

    def spawn_food(self) -> Point | None:
        occupied = set(self.snake)
        empty_cells = [
            Point(x, y)
            for y in range(GRID_HEIGHT)
            for x in range(GRID_WIDTH)
            if Point(x, y) not in occupied
        ]
        if not empty_cells:
            return None
        return random.choice(empty_cells)

    async def run(self) -> None:
        """Main loop. Async so the browser gets control back every frame (pygbag)."""
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    running = self.handle_key(event.key)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    self.touch_start = event.pos
                elif event.type == pygame.MOUSEBUTTONUP and self.touch_start:
                    self.handle_swipe(self.touch_start, event.pos)
                    self.touch_start = None

            if self.state == GameState.PLAYING:
                self.update()

            self.draw()
            pygame.display.flip()
            self.clock.tick(FPS)
            await asyncio.sleep(0)

        pygame.quit()

    def handle_swipe(self, start: tuple[int, int], end: tuple[int, int]) -> None:
        """Touch and mouse: a tap starts or restarts, a swipe steers."""
        dx, dy = end[0] - start[0], end[1] - start[1]
        if max(abs(dx), abs(dy)) < SWIPE_MIN_PX:
            self.handle_key(pygame.K_SPACE)
            return
        if self.state != GameState.PLAYING and abs(dx) > abs(dy):
            self.handle_key(pygame.K_m)  # phones have no M key: swipe sideways between games instead
            return
        direction = (RIGHT if dx > 0 else LEFT) if abs(dx) > abs(dy) else (DOWN if dy > 0 else UP)
        key = {UP: pygame.K_UP, DOWN: pygame.K_DOWN, LEFT: pygame.K_LEFT, RIGHT: pygame.K_RIGHT}[direction]
        self.handle_key(key)

    def handle_key(self, key: int) -> bool:
        if key == pygame.K_ESCAPE:
            return WEB  # a web page cannot be quit; on desktop Esc exits

        if key in (pygame.K_RETURN, pygame.K_SPACE):
            if self.state in (GameState.START, GameState.GAME_OVER):
                self.reset()
                self.state = GameState.PLAYING
            return True

        if key == pygame.K_m and self.state in (GameState.START, GameState.GAME_OVER):
            self.mode = MODES[(MODES.index(self.mode) + 1) % len(MODES)]
            return True

        if key == pygame.K_p:
            if self.state == GameState.PLAYING:
                self.state = GameState.PAUSED
            elif self.state == GameState.PAUSED:
                self.state = GameState.PLAYING
                self.last_move_ms = pygame.time.get_ticks()
            return True

        requested = {
            pygame.K_UP: UP,
            pygame.K_w: UP,
            pygame.K_DOWN: DOWN,
            pygame.K_s: DOWN,
            pygame.K_LEFT: LEFT,
            pygame.K_a: LEFT,
            pygame.K_RIGHT: RIGHT,
            pygame.K_d: RIGHT,
        }.get(key)

        if requested and self.state == GameState.PLAYING:
            # judge each turn against the last queued one, not the current heading
            last = self.turns[-1] if self.turns else self.direction
            if requested != last and not self.is_opposite(requested, last) and len(self.turns) < MAX_QUEUED_TURNS:
                self.turns.append(requested)

        return True

    @property
    def pending_direction(self) -> Point:
        """The heading the snake will take on its next move."""
        return self.turns[0] if self.turns else self.direction

    @property
    def best(self) -> int:
        return self.scores.best[self.mode]

    @staticmethod
    def is_opposite(first: Point, second: Point) -> bool:
        return first.x + second.x == 0 and first.y + second.y == 0

    def update(self) -> None:
        now = pygame.time.get_ticks()
        if now - self.last_move_ms < self.move_delay_ms:
            return

        self.last_move_ms = now
        if self.turns:
            self.direction = self.turns.pop(0)
        new_head = self.snake[0] + self.direction
        if self.mode == "wrap":
            new_head = Point(new_head.x % GRID_WIDTH, new_head.y % GRID_HEIGHT)

        if self.hit_wall(new_head) or self.hit_self(new_head):
            self.end_game()
            return

        self.snake.insert(0, new_head)

        if new_head == self.food:
            self.score += 1
            self.move_delay_ms = max(
                MIN_MOVE_MS,
                BASE_MOVE_MS - self.score * SPEEDUP_PER_FOOD_MS,
            )
            self.food = self.spawn_food()
            if self.food is None:
                self.game_over_title = "YOU WIN"
                self.game_over_subtitle = "Press Space or Enter to play again"
                self.end_game()
        else:
            self.snake.pop()

    def end_game(self) -> None:
        self.new_best = self.scores.record(self.mode, self.score)
        if self.new_best and self.game_over_title == "GAME OVER":
            self.game_over_title = "NEW BEST"
        self.state = GameState.GAME_OVER

    @staticmethod
    def hit_wall(point: Point) -> bool:
        return point.x < 0 or point.x >= GRID_WIDTH or point.y < 0 or point.y >= GRID_HEIGHT

    def hit_self(self, point: Point) -> bool:
        return point in self.snake[:-1]

    def draw(self) -> None:
        self.screen.fill(BACKGROUND)
        self.draw_header()
        self.draw_board()
        if self.food is not None:
            self.draw_food()
        self.draw_snake()

        if self.state == GameState.START:
            self.draw_overlay("SNAKE", "Press Space, Enter or tap to start")
        elif self.state == GameState.PAUSED:
            self.draw_overlay("PAUSED", "Press P to resume")
        elif self.state == GameState.GAME_OVER:
            self.draw_overlay(self.game_over_title, self.game_over_subtitle)

        self.screen.blit(self.scanlines, (0, 0))

    @staticmethod
    def make_scanlines() -> pygame.Surface:
        """A faint CRT scanline overlay, drawn once and reused every frame."""
        lines = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        for y in range(0, WINDOW_HEIGHT, 3):
            pygame.draw.line(lines, (0, 0, 0, 55), (0, y), (WINDOW_WIDTH, y))
        return lines

    def draw_header(self) -> None:
        pygame.draw.rect(self.screen, HEADER, (0, 0, WINDOW_WIDTH, HEADER_HEIGHT))
        score_surface = self.font.render(f"Score: {self.score}", True, TEXT)
        speed_surface = self.font.render(
            f"Speed: {self.current_speed_label()}    Best: {max(self.best, self.score)}    Mode: {self.mode.title()}",
            True,
            MUTED_TEXT,
        )
        controls = "Arrows/WASD or swipe  P to pause" if WEB else "Arrows/WASD to move  P to pause  Esc to quit"
        help_surface = self.small_font.render(controls, True, MUTED_TEXT)

        self.screen.blit(score_surface, (24, 15))
        self.screen.blit(speed_surface, (24, 42))
        self.screen.blit(help_surface, (WINDOW_WIDTH - help_surface.get_width() - 24, 27))

    def current_speed_label(self) -> str:
        level = 1 + (BASE_MOVE_MS - self.move_delay_ms) // 12
        return str(max(1, level))

    def draw_board(self) -> None:
        board_rect = pygame.Rect(0, HEADER_HEIGHT, BOARD_WIDTH, BOARD_HEIGHT)
        pygame.draw.rect(self.screen, BOARD, board_rect)

        for x in range(0, BOARD_WIDTH + 1, CELL_SIZE):
            pygame.draw.line(
                self.screen,
                GRID,
                (x, HEADER_HEIGHT),
                (x, HEADER_HEIGHT + BOARD_HEIGHT),
            )
        for y in range(HEADER_HEIGHT, HEADER_HEIGHT + BOARD_HEIGHT + 1, CELL_SIZE):
            pygame.draw.line(self.screen, GRID, (0, y), (BOARD_WIDTH, y))

        pygame.draw.rect(self.screen, ACCENT, board_rect, 2)

    def draw_food(self) -> None:
        rect = self.cell_rect(self.food).inflate(-6, -6)
        pygame.draw.ellipse(self.screen, FOOD, rect)
        highlight = pygame.Rect(rect.x + 6, rect.y + 5, rect.width // 3, rect.height // 3)
        pygame.draw.ellipse(self.screen, FOOD_HIGHLIGHT, highlight)

    def draw_snake(self) -> None:
        for index, segment in enumerate(reversed(self.snake)):
            real_index = len(self.snake) - 1 - index
            rect = self.cell_rect(segment).inflate(-3, -3)
            color = SNAKE_HEAD if real_index == 0 else (
                SNAKE_BODY if real_index % 2 == 0 else SNAKE_BODY_ALT
            )
            pygame.draw.rect(self.screen, color, rect, border_radius=2)

        head_rect = self.cell_rect(self.snake[0]).inflate(-10, -10)
        pygame.draw.rect(self.screen, BACKGROUND, head_rect)

    @staticmethod
    def cell_rect(point: Point) -> pygame.Rect:
        return pygame.Rect(
            point.x * CELL_SIZE,
            HEADER_HEIGHT + point.y * CELL_SIZE,
            CELL_SIZE,
            CELL_SIZE,
        )

    def draw_overlay(self, title: str, subtitle: str) -> None:
        overlay = pygame.Surface((WINDOW_WIDTH, BOARD_HEIGHT), pygame.SRCALPHA)
        overlay.fill(OVERLAY)
        self.screen.blit(overlay, (0, HEADER_HEIGHT))

        title_surface = self.large_font.render(title, True, TITLE)
        subtitle_surface = self.font.render(subtitle, True, MUTED_TEXT)
        switch = "Swipe sideways or press M" if WEB else "Press M"
        if self.state == GameState.PAUSED:
            hint = "Eat food, grow longer, and avoid the walls."
        elif self.mode == "wrap":
            hint = f"Wrap mode: the walls wrap around. {switch} for Classic."
        else:
            hint = f"Classic mode: avoid the walls. {switch} for Wrap."
        hint_surface = self.small_font.render(hint, True, MUTED_TEXT)

        center_y = HEADER_HEIGHT + BOARD_HEIGHT // 2
        self.screen.blit(
            title_surface,
            title_surface.get_rect(center=(WINDOW_WIDTH // 2, center_y - 48)),
        )
        self.screen.blit(
            subtitle_surface,
            subtitle_surface.get_rect(center=(WINDOW_WIDTH // 2, center_y + 8)),
        )
        self.screen.blit(
            hint_surface,
            hint_surface.get_rect(center=(WINDOW_WIDTH // 2, center_y + 42)),
        )


async def main() -> None:
    await SnakeGame().run()


if __name__ == "__main__":
    asyncio.run(main())
