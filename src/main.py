from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum
from typing import Optional

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

BACKGROUND = (9, 14, 25)
HEADER = (13, 22, 38)
BOARD = (11, 18, 32)
GRID = (22, 34, 54)
SNAKE_HEAD = (110, 231, 183)
SNAKE_BODY = (45, 188, 143)
SNAKE_BODY_ALT = (38, 164, 128)
FOOD = (255, 111, 97)
FOOD_HIGHLIGHT = (255, 179, 148)
TEXT = (226, 235, 245)
MUTED_TEXT = (139, 154, 176)
OVERLAY = (6, 10, 20, 188)
ACCENT = (123, 211, 255)


class GameState(Enum):
    START = "start"
    PLAYING = "playing"
    PAUSED = "paused"
    GAME_OVER = "game_over"


@dataclass(frozen=True)
class Point:
    x: int
    y: int

    def __add__(self, other: "Point") -> "Point":
        return Point(self.x + other.x, self.y + other.y)


UP = Point(0, -1)
DOWN = Point(0, 1)
LEFT = Point(-1, 0)
RIGHT = Point(1, 0)


class SnakeGame:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("Snake")
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 30)
        self.large_font = pygame.font.Font(None, 64)
        self.small_font = pygame.font.Font(None, 24)
        self.state = GameState.START
        self.game_over_title = "GAME OVER"
        self.game_over_subtitle = "Press Space or Enter to restart"
        self.reset()

    def reset(self) -> None:
        center = Point(GRID_WIDTH // 2, GRID_HEIGHT // 2)
        self.snake = [
            center,
            Point(center.x - 1, center.y),
            Point(center.x - 2, center.y),
        ]
        self.direction = RIGHT
        self.pending_direction = RIGHT
        self.food = self.spawn_food()
        self.score = 0
        self.move_delay_ms = BASE_MOVE_MS
        self.last_move_ms = pygame.time.get_ticks()
        self.game_over_title = "GAME OVER"
        self.game_over_subtitle = "Press Space or Enter to restart"

    def spawn_food(self) -> Optional[Point]:
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

    def run(self) -> None:
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    running = self.handle_key(event.key)

            if self.state == GameState.PLAYING:
                self.update()

            self.draw()
            pygame.display.flip()
            self.clock.tick(FPS)

        pygame.quit()

    def handle_key(self, key: int) -> bool:
        if key == pygame.K_ESCAPE:
            return False

        if key in (pygame.K_RETURN, pygame.K_SPACE):
            if self.state in (GameState.START, GameState.GAME_OVER):
                self.reset()
                self.state = GameState.PLAYING
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
            if not self.is_opposite(requested, self.direction):
                self.pending_direction = requested

        return True

    @staticmethod
    def is_opposite(first: Point, second: Point) -> bool:
        return first.x + second.x == 0 and first.y + second.y == 0

    def update(self) -> None:
        now = pygame.time.get_ticks()
        if now - self.last_move_ms < self.move_delay_ms:
            return

        self.last_move_ms = now
        self.direction = self.pending_direction
        new_head = self.snake[0] + self.direction

        if self.hit_wall(new_head) or self.hit_self(new_head):
            self.state = GameState.GAME_OVER
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
                self.state = GameState.GAME_OVER
        else:
            self.snake.pop()

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
            self.draw_overlay("SNAKE", "Press Space or Enter to start")
        elif self.state == GameState.PAUSED:
            self.draw_overlay("PAUSED", "Press P to resume")
        elif self.state == GameState.GAME_OVER:
            self.draw_overlay(self.game_over_title, self.game_over_subtitle)

    def draw_header(self) -> None:
        pygame.draw.rect(self.screen, HEADER, (0, 0, WINDOW_WIDTH, HEADER_HEIGHT))
        score_surface = self.font.render(f"Score: {self.score}", True, TEXT)
        speed_surface = self.font.render(f"Speed: {self.current_speed_label()}", True, MUTED_TEXT)
        help_surface = self.small_font.render("Arrows/WASD to move  P to pause  Esc to quit", True, MUTED_TEXT)

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
            pygame.draw.rect(self.screen, color, rect, border_radius=6)

        head_rect = self.cell_rect(self.snake[0]).inflate(-8, -8)
        pygame.draw.rect(self.screen, (206, 255, 235), head_rect, border_radius=4)

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

        title_surface = self.large_font.render(title, True, TEXT)
        subtitle_surface = self.font.render(subtitle, True, MUTED_TEXT)
        hint_surface = self.small_font.render("Eat food, grow longer, and avoid the walls.", True, MUTED_TEXT)

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


def main() -> None:
    SnakeGame().run()


if __name__ == "__main__":
    main()
