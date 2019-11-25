import pygame

from numpy import ndarray, sign

from math import sqrt, sin, cos, atan, pi
from random import randint, random, choice

SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
HUD_HEIGHT = 72
HUD_RECT = pygame.Rect(0, SCREEN_HEIGHT, SCREEN_WIDTH, HUD_HEIGHT)
TILE_SIZE = 4
TILE_COLUMNS = SCREEN_WIDTH // TILE_SIZE
TILE_ROWS = SCREEN_HEIGHT // TILE_SIZE
GRAVITY = 3.0e-04
SMOKE_G = -4.9e-06
SHELL_SPEED = 0.69
FIRE_RATE = 256
SHELL_TIME = -2.4e5
PARTICLE_SPEED = 0.24
PARTICLE_SPEED_RANGE = 0.12
PARTICLE_TIME = -1024
PARTICLE_TIME_RANGE = 256
SMOKE_TIME = -2048
SMOKE_TIME_RANGE = 256
PIECE_WIDTH = 21
PIECE_HEIGHT = 13
INDICATOR_LENGTH = 49
TURN_RATE = pi / 4096
TEXT_INTERVAL = 256
TEXT_SPEED = 2.0e-04

def tile_at(x, y, tls):    
    column = x // TILE_SIZE
    row = y // TILE_SIZE
    if (0 <= column < TILE_COLUMNS and
        0 <= row < TILE_ROWS):
        return tls[column, row]

def tiles_at(r, tls):
    column_bounds = [r.left // TILE_SIZE, -(-r.right // TILE_SIZE)]
    row_bounds = [r.top // TILE_SIZE, -(-r.bottom // TILE_SIZE)]
    column_bounds = [(0 if b < 0 else (TILE_COLUMNS - 1 if b >= TILE_COLUMNS else b))
                     for b in column_bounds]
    row_bounds = [(0 if b < 0 else (TILE_COLUMNS - 1 if b >= TILE_ROWS else b))
                     for b in row_bounds]
    return tls[column_bounds[0]:column_bounds[1],
               row_bounds[0]:row_bounds[1]].flatten().tolist()
    

class Particle:
    def __init__(self, x, y, dx, dy, c, t, s, i):
        self.x = x
        self.y = y
        self.dx = dx
        self.dy = dy
        self.color = c
        self.time = t
        self.stage = s
        self.id = i
        
    def update(self, tls, pcs, pts, e):
        self.time += e
        if self.time > 0:
            self.time = 0
        if self.stage < 2:
            self.dy += GRAVITY * e
            if not (self.stage and randint(0, 16)):
                # Create smoke trail.
                pts.append(Particle(self.x + randint(-2, 2), self.y + randint(-2, 2),
                                    0, 0, pygame.Color(64, 64, 64),
                                    SMOKE_TIME + randint(-SMOKE_TIME_RANGE, SMOKE_TIME_RANGE),
                                    2, -1))
        else:
            self.dy += SMOKE_G * e
        ct = tile_at(int(self.x), int(self.y), tls)
        if ct:
            if self.stage < 2:
                # This particle is not smoke.
                if ct.type:
                    self.time = 0
                else:
                    for p in pcs:
                        if (p.r.left <= self.x <= p.r.right and
                            p.r.top <= self.y <= p.r.bottom):
                                if not self.stage and self.id != p.id:
                                    # Only shells die to pieces.
                                    self.time = 0
                                elif self.stage == 1 and self.id > -1:
                                    # Stage 1 particles do damage then lose id
                                    p.take_hit()
                                    if p.id != self.id:
                                        pcs[self.id - 1].get_points()
                                    self.id = -1
                                break
                ct.set_type(0)
                if not self.time and not self.stage:
                    # Shell explodes.
                    pcs[self.id - 1].register_shot(self)
                    th = 0
                    while th < 2 * pi:
                        s = PARTICLE_SPEED + (random() * PARTICLE_SPEED_RANGE)
                        pts.append(Particle(self.x, self.y,
                                            s * cos(th),
                                            s * sin(th),
                                            self.color, PARTICLE_TIME +
                                            randint(-PARTICLE_TIME_RANGE,
                                                    PARTICLE_TIME_RANGE),
                                            1, self.id))
                        th += random() * pi / 96
        elif self.y >= SCREEN_HEIGHT or self.x < 0 or self.x >= SCREEN_WIDTH:
            self.time = 0
            pcs[self.id - 1].register_shot(self)
        self.x += self.dx * e
        self.y += self.dy * e

    def draw(self, s, tls, dts):
        if self.stage:
            s.set_at((int(self.x), int(self.y)), self.color)
            dt = tile_at(int(self.x), int(self.y), tls)
            if dt:
                dts.add(dt)
        else:
            pygame.draw.circle(s, self.color, (int(self.x), int(self.y)), 2, 1)
            r = pygame.Rect(self.x - 2, self.y - 2, 4, 4)
            dts.update(tiles_at(r, tls))


class FloatText:
    def __init__(self, x, y, f, t, c):
        self.font = f
        self.color = c
        self.set_text(t)
        self.r = pygame.Rect(x - int(self.s.get_width() / 2),
                             y - int(self.s.get_height() / 2),
                             self.s.get_width(), self.s.get_height())

    def set_text(self, t):
        self.s = self.font.render(t, True, self.color)

    def draw(self, s, drs=None):
        s.blit(self.s, self.r)
        if drs:
            drs.append(self.r)


class Piece:
    def __init__(self, x, y, i, f):
        self.id = i
        self.r = pygame.Rect(x - int(PIECE_WIDTH / 2),
                             y - int(PIECE_HEIGHT / 2),
                             PIECE_WIDTH, PIECE_HEIGHT)
        self.x = x
        self.y = y
        self.color = pygame.Color(i % 4 * 85, (i + 1) % 4 * 85,
                                  (i + 2) % 4 * 85)
        self.dx = 0
        self.dy = 0
        self.th = -pi / 2
        self.dth = 0
        self.indicator = (self.r.center[0],
                          self.r.center[1] - INDICATOR_LENGTH)
        self.last_indicator = self.indicator
        self.offset = (0, -INDICATOR_LENGTH)
        self.last_offset = self.offset
        self.indicator_color = pygame.Color('white') - self.color
        self.fire_speed = SHELL_SPEED
        self.fire_counter = 0
        self.firing = False
        self.font = f
        self.text = []
        self.text_counter = 0
        self.damage = 0
        self.last_damage = 0
        self.points = 0
        self.last_points = 0
        self.shot_landed = True
        self.shot_history = {}

    def point_at(self, pos):
        offset = (pos[0] - self.r.center[0], pos[1] - self.r.center[1])
        distance = sqrt(offset[0] * offset[0] + offset[1] * offset[1])
        if not distance:
            return
        scale = INDICATOR_LENGTH / distance
        self.offset = (offset[0] * scale, offset[1] * scale)
        self.indicator = (self.r.center[0] + int(self.offset[0]),
                          self.r.center[1] + int(self.offset[1]))

    def turn(self, dth):
        self.dth = dth

    def stop_turn(self, s):
        if (s < 0 and self.dth < 0) or (s > 0 and self.dth > 0):
            self.dth = 0

    def register_shot(self, sh):
        self.shot_history[self.th] = (int(sh.x), int(sh.y), sh.dx, sh.dy)
        self.shot_landed = True

    def bot_aim(self, tgt):
        x = tgt[0] - self.r.center[0]
        y = tgt[1] - self.r.center[1]
        A = GRAVITY * x ** 2 / (2 * SHELL_SPEED ** 2)
        B = x ** 2 - 4 * A * (A - y)
        if B < 0:
            return False
        if x > 0:
            self.th = atan((-x - sqrt(B)) / (2 * A))
        else:
            self.th = atan((-x + sqrt(B)) / (2 * A)) + pi
        self.offset = (cos(self.th) * INDICATOR_LENGTH, sin(self.th) * INDICATOR_LENGTH)
        if not self.shot_landed:
            return False
        '''
        if self.shot_history:
            if len(self.shot_history) > 1:
                # We have at least two shots to compare
                closest_left = -1
                closest_right = -1
            else:
                # We have only taken one shot
                self.th += sign(tgt[0] - self.shot_history[0][0]) * random() * pi / 8
        else:
            # This is the first shot, pick randomly in the right direction
            self.th += sign(tgt[0] - self.r.center[0]) * random() * pi / 4
        self.th_history.append(self.th)
        self.offset = (cos(self.th) * INDICATOR_LENGTH, sin(self.th) * INDICATOR_LENGTH)'''
        return True

    def fire(self, pts):
        # Fire a shell.
        scale = self.fire_speed / INDICATOR_LENGTH
        dx = self.offset[0] * scale
        dy = self.offset[1] * scale
        pts.append(Particle(self.x, self.y, dx, dy, pygame.Color('white'),
                            SHELL_TIME, 0, self.id))
        self.fire_counter -= FIRE_RATE
        self.last_offset = self.offset
        self.shot_landed = False

    def toggle_firing(self):
        self.firing = not self.firing
        if self.firing and self.fire_counter > 0:
            self.fire_counter = 0
            

    def move(self, dx):
        self.dx += dx

    def stop_move(self, s):
        if (s < 0 and self.dx < 0) or (s > 0 and self.dx > 0):
            self.dx = 0

    def jump(self, ddy):
        if not self.dy:
            self.dy = ddy

    def update(self, tls, pts, e):
        br = pygame.Rect(self.r.left, self.r.bottom - TILE_SIZE,
                         self.r.width, TILE_SIZE)
        cts = tiles_at(br, tls)
        for ct in cts:
            if ct.type:
                self.dy = 0
                break
        else:
            self.dy += GRAVITY * e
        if self.dx or self.dy:
            dx = self.dx * e
            dy = self.dy * e
            self.x += dx
            self.y += dy
            self.r.x = self.x - int(self.r.width / 2)
            self.r.y = self.y - int(self.r.height / 2)
            for t in self.text:
                t.r.x += dx
                t.r.y += dy
        if self.dth:
            self.th += self.dth * e
            self.offset = (cos(self.th) * INDICATOR_LENGTH, sin(self.th) * INDICATOR_LENGTH)
        self.indicator = (int(self.x + self.offset[0]), int(self.y + self.offset[1]))
        self.last_indicator = (int(self.x + self.last_offset[0]), int(self.y + self.last_offset[1]))
        self.fire_counter += e
        if self.firing and self.fire_counter > 0:
            self.fire(particles)
        self.text_counter += e
        if self.text_counter > 0:
            dy = e * TEXT_INTERVAL * -TEXT_SPEED
            self.text_counter -= TEXT_INTERVAL
            if self.damage > self.last_damage:
                self.text.append(FloatText(self.r.center[0], self.r.bottom, self.font,
                                           str(self.damage - self.last_damage),
                                           pygame.Color('red')))
                self.last_damage = self.damage
                if self.text[-1].r.bottom + self.text[-1].r.h > self.r.center[1]:
                    dy -= self.text[-1].r.height
            for t in self.text:
                t.r.y += dy
            dy = 0
            if self.points > self.last_points:
                self.text.append(FloatText(self.r.center[0], self.r.bottom, self.font,
                                           str(self.points - self.last_points),
                                           pygame.Color('green')))
                self.last_points = self.points
                if self.text[-1].r.bottom + self.text[-1].r.h > self.r.center[1]:
                    dy -= self.text[-1].r.height
            for t in self.text:
                t.r.y += dy
        self.text = [t for t in self.text if t.r.top > self.r.center[1] - INDICATOR_LENGTH]

    def take_hit(self):
        self.text_counter = -TEXT_INTERVAL
        self.damage += 1

    def get_points(self):
        self.text_counter = -TEXT_INTERVAL
        self.points += 1

    def draw(self, s, tls, dts):
        s.fill(self.color, self.r)
        pygame.draw.line(s, self.indicator_color // pygame.Color(2, 2, 2), self.r.center, self.last_indicator, 2)
        pygame.draw.line(s, self.indicator_color, self.r.center, self.indicator, 2)
        for t in self.text:
            t.draw(s)
        r = pygame.Rect(self.r.center[0] - INDICATOR_LENGTH - 1,
                        self.r.center[1] - INDICATOR_LENGTH - 1,
                        INDICATOR_LENGTH * 2 + 2, INDICATOR_LENGTH * 2 + 2)
        dts.update(tiles_at(r, tls))

class Tile:
    def __init__(self, c, r, t):
        self.r = pygame.Rect(c * TILE_SIZE, r * TILE_SIZE, TILE_SIZE, TILE_SIZE)
        self.s = pygame.Surface((TILE_SIZE, TILE_SIZE))
        self.set_type(t)

    def set_type(self, t):
        self.type = t
        if t == 0:
            self.s.fill(0)
        elif t == 1:
            self.s.fill((127, 127, 127))

    def draw(self, s):
        s.blit(self.s, self.r)
        

def reset(tls, dts, pcs, pts, ht, f):
    terrain = [TILE_ROWS // 5 for c in range(0, TILE_COLUMNS)]
    steps = [-1] + [1] * 3 + [2] * 2
    for c in range(1, TILE_COLUMNS // 2 + 1):
        terrain[TILE_COLUMNS // 2 - c] = terrain[TILE_COLUMNS // 2 - c + 1] + choice(steps)
    for c in range(TILE_COLUMNS // 2 + 1, TILE_COLUMNS):
        terrain[c] = terrain[c - 1] + choice(steps)
    for r in range(0, TILE_ROWS):
        for c in range(0, TILE_COLUMNS):
            tls[c][r] = Tile(c, r, 0 if r < terrain[c] else 1)
    dts.clear()
    dts.update(tiles.flatten().tolist())
    pcs.clear()
    pcs.append(Piece(SCREEN_WIDTH / 7., SCREEN_HEIGHT / 2., 1, f))
    pcs.append(Piece(SCREEN_WIDTH * 6 / 7., SCREEN_HEIGHT / 2., 2, f))
    pts.clear()
    ht.clear()
    ht.append(FloatText(SCREEN_WIDTH / 4, SCREEN_HEIGHT + HUD_HEIGHT / 4, f, 'points: 0', pieces[0].color))
    ht.append(FloatText(SCREEN_WIDTH / 4, SCREEN_HEIGHT + HUD_HEIGHT  * 3 / 4, f, 'damage: 0', pieces[0].color))
    ht.append(FloatText(SCREEN_WIDTH * 3 / 4, SCREEN_HEIGHT + HUD_HEIGHT / 4, f, 'points: 0', pieces[1].color))
    ht.append(FloatText(SCREEN_WIDTH * 3 / 4, SCREEN_HEIGHT + HUD_HEIGHT * 3 / 4, f, 'damage: 0', pieces[1].color))

        

pygame.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT + HUD_HEIGHT), pygame.FULLSCREEN)
font = pygame.font.SysFont('freesansbold', 17)
tiles = ndarray((TILE_COLUMNS, TILE_ROWS), Tile)
dirty = set()
pieces = []
particles = []
hud_text = []
reset(tiles, dirty, pieces, particles, hud_text, font)
turn = 0
done = False
last_ticks = pygame.time.get_ticks()
while not done:
    ticks = pygame.time.get_ticks()
    elapsed = ticks - last_ticks
    last_ticks = ticks
    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            done = True
        elif e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                done = True
            elif e.key == pygame.K_r:
                reset(tiles, dirty, pieces, particles, hud_text, font)
                last_ticks = pygame.time.get_ticks()
                turn = 0
            elif e.key == pygame.K_a:
                next_turn = turn + 1
                if next_turn >= len(pieces):
                    next_turn = 0
                pieces[turn].bot_aim(pieces[next_turn].r.center)
                pieces[turn].fire(particles)
                turn = next_turn
            elif e.key == pygame.K_q:
                pieces[0].turn(-TURN_RATE)
            elif e.key == pygame.K_e:
                pieces[0].turn(TURN_RATE)
            elif e.key == pygame.K_SPACE:
                pieces[0].toggle_firing()
            elif e.key == pygame.K_KP7:
                pieces[1].turn(-TURN_RATE)
            elif e.key == pygame.K_KP9:
                pieces[1].turn(TURN_RATE)
            elif e.key == pygame.K_KP_ENTER:
                pieces[1].toggle_firing()
        elif e.type == pygame.KEYUP:
            if e.key == pygame.K_q:
                pieces[0].stop_turn(-1)
            elif e.key == pygame.K_e:
                pieces[0].stop_turn(1)
            if e.key == pygame.K_KP7:
                pieces[1].stop_turn(-1)
            elif e.key == pygame.K_KP9:
                pieces[1].stop_turn(1)
        elif e.type == pygame.MOUSEBUTTONUP:
            pieces[turn].fire(particles)
            turn += 1
            if turn >= len(pieces):
                turn = 0
        elif e.type == pygame.MOUSEMOTION:
            pieces[turn].point_at(pygame.mouse.get_pos())
    for d in dirty:
        d.draw(screen)
    screen.fill(0, HUD_RECT)
    i = 0
    for t in hud_text:
        p = i % 2 == 0
        t.set_text(('points' if p else 'damage') + ': ' + str(pieces[i // 2].points if p else
                                                              pieces[i // 2].damage))
        t.draw(screen)
        i += 1
    dirty = set()
    for p in pieces:
        p.update(tiles, particles, elapsed)
        p.draw(screen, tiles, dirty)
    for p in particles:
        p.update(tiles, pieces, particles, elapsed)
        p.draw(screen, tiles, dirty)
    particles = [p for p in particles if p.time]
    pygame.display.flip()

pygame.quit()
        
        
