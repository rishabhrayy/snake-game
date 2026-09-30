"""Game-logic tests. Run headless: SDL's dummy video driver needs no window."""

import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pygame  # noqa: E402
import pytest  # noqa: E402

import main  # noqa: E402
from main import DOWN, LEFT, RIGHT, UP, GameState, Point, SnakeGame  # noqa: E402


@pytest.fixture
def game():
    g = SnakeGame()
    g.handle_key(pygame.K_SPACE)
    return g


def step(g: SnakeGame) -> None:
    """Advance exactly one move, ignoring the real-time delay."""
    g.last_move_ms = -10**9
    g.update()


def test_starts_on_space(game):
    assert game.state == GameState.PLAYING
    assert len(game.snake) == 3


def test_cannot_reverse_into_itself(game):
    game.handle_key(pygame.K_LEFT)  # moving right, so left is ignored
    assert game.pending_direction == RIGHT


def test_eating_grows_and_speeds_up(game):
    head = game.snake[0]
    game.food = head + RIGHT
    delay = game.move_delay_ms
    step(game)
    assert len(game.snake) == 4
    assert game.score == 1
    assert game.move_delay_ms < delay


def test_wall_ends_the_game_and_records_best(game):
    game.snake = [Point(main.GRID_WIDTH - 1, 5), Point(main.GRID_WIDTH - 2, 5), Point(main.GRID_WIDTH - 3, 5)]
    game.score = 7
    step(game)
    assert game.state == GameState.GAME_OVER
    assert game.best == 7


def test_running_into_the_body_ends_the_game(game):
    # a loop: head moves up into its own body
    game.snake = [Point(5, 5), Point(6, 5), Point(6, 4), Point(5, 4), Point(4, 4)]
    game.direction = game.pending_direction = UP
    step(game)
    assert game.state == GameState.GAME_OVER


def test_swipes_steer_and_taps_restart(game):
    game.handle_swipe((100, 100), (100, 180))
    assert game.pending_direction == DOWN
    game.state = GameState.GAME_OVER
    game.handle_swipe((100, 100), (104, 102))  # a tap
    assert game.state == GameState.PLAYING


def test_pause_toggles(game):
    game.handle_key(pygame.K_p)
    assert game.state == GameState.PAUSED
    game.handle_key(pygame.K_p)
    assert game.state == GameState.PLAYING


def test_food_never_spawns_on_the_snake(game):
    for _ in range(200):
        assert game.spawn_food() not in game.snake


def test_escape_quits_on_desktop_only(game, monkeypatch):
    monkeypatch.setattr(main, "WEB", False)
    assert game.handle_key(pygame.K_ESCAPE) is False
    monkeypatch.setattr(main, "WEB", True)
    assert game.handle_key(pygame.K_ESCAPE) is True
