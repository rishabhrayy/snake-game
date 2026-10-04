"""Record assets/demo.gif: a breadth-first-search autopilot plays the real game headlessly.

Usage:  python scripts/record_demo.py
"""

import os
import random
import sys
from collections import deque
from pathlib import Path

os.environ["SDL_VIDEODRIVER"] = "dummy"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pygame  # noqa: E402
from PIL import Image  # noqa: E402

from main import DOWN, LEFT, RIGHT, UP, GameState, Scores, SnakeGame  # noqa: E402

KEYS = {UP: pygame.K_UP, DOWN: pygame.K_DOWN, LEFT: pygame.K_LEFT, RIGHT: pygame.K_RIGHT}


def next_move(g: SnakeGame):
    """Shortest safe path to the food; otherwise any move that does not die immediately."""
    blocked = set(g.snake[:-1])
    head = g.snake[0]
    queue, first = deque([head]), {head: None}
    while queue:
        cell = queue.popleft()
        if cell == g.food:
            while first[cell] is not None and first[first[cell]] is not None:
                cell = first[cell]
            return next(d for d in KEYS if head + d == cell)
        for d in KEYS:
            n = cell + d
            if n not in first and n not in blocked and not g.hit_wall(n):
                first[n] = cell
                queue.append(n)
    safe = [d for d in KEYS if not g.hit_wall(head + d) and head + d not in blocked]
    return random.choice(safe) if safe else g.direction


def frame(g: SnakeGame) -> Image.Image:
    g.draw()
    raw = pygame.image.tobytes(g.screen, "RGB")
    img = Image.frombytes("RGB", g.screen.get_size(), raw)
    return img.resize((img.width * 2 // 3, img.height * 2 // 3), Image.LANCZOS)


def main_() -> None:
    random.seed(7)
    g = SnakeGame(Scores(path=None))  # the recording never touches your saved best
    frames = [frame(g)] * 12  # title screen
    g.handle_key(pygame.K_SPACE)
    for _ in range(260):
        if g.state != GameState.PLAYING:
            break
        g.handle_key(KEYS[next_move(g)])
        g.last_move_ms = -10**9
        g.update()
        frames.append(frame(g))
    frames += [frame(g)] * 15
    out = ROOT / "assets" / "demo.gif"
    out.parent.mkdir(exist_ok=True)
    palette = [f.convert("P", palette=Image.ADAPTIVE, colors=256) for f in frames]
    palette[0].save(out, save_all=True, append_images=palette[1:], duration=70, loop=0, optimize=True)
    print(f"wrote {out} ({len(frames)} frames, score {g.score})")


if __name__ == "__main__":
    main_()
