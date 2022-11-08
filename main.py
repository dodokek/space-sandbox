'''
Libraries:
pygame + pygame_widgets - graphics
deque  - Planets' and Rocket's trails tracking
math   - smoothing function for zooming
time   - timer on screen
sys    - stopping the application
os     - resources for graphics 
'''


import pygame as pg
import pygame_widgets as pw

import math
import time
import sys
import os

from pygame_widgets.slider import Slider
from collections import deque


class Viewport:
    def __init__(self):
        self.scaling = INIT_SCALING
        self.zoom_level = INIT_SCALING
        self.delta_zoom = 0.1

        self.shift = INIT_SHIFT
        self.shifting = False

    # TODO make scaling work to the center of screen or to a mouse
    def scale(self, coord, mouse_pos=pg.Vector2(0, 0)):
        return pg.Vector2((coord[0] - W/2 + mouse_pos.x) / self.scaling + W/2, (coord[1] - H/2 + mouse_pos.y) / self.scaling + H/2) + self.shift

    def unscale(self, coord):
        coord = coord - self.shift
        return pg.Vector2((coord[0] - W/2) * self.scaling + W/2, (coord[1] - H/2) * self.scaling + H/2)

    def update(self, zoom):
        self.zoom_level += zoom * self.delta_zoom

        if self.zoom_level < 1:
            self.scaling = 1 / (1 + math.exp(-self.zoom_level))
        else:
            self.scaling = self.zoom_level * self.zoom_level

        for e in entities:
            if e.has_trail:
                for i in range(len(e.trail)):
                    e.trail[i] = self.scale(e.trail_real[i])


# *                                    (m, kg, secs)
class Entity:  # * all the input parameters are real, except coordinates
    def __init__(self, coordinates, init_velocity, radius, mass, color, has_trail=True):
        self.coordinates = pg.math.Vector2(coordinates)
        self.position = self.coordinates / SCALE
        self.radius = radius

        self.velocity = pg.Vector2(init_velocity)
        self.acceleration = pg.Vector2(0, 0)
        self.mass = mass

        self.color = color

        if has_trail and type(self) != PlanetStatic:
            self.has_trail = True
            self.trail = deque([VIEWPORT.scale(self.coordinates), VIEWPORT.scale(self.coordinates)], maxlen=TRAILSIZE)
            self.trail_real = deque([self.position * SCALE, self.position * SCALE], maxlen=TRAILSIZE)
        else:
            self.has_trail = False

    def update(self):
        if type(self) == PlanetStatic:
            self.coordinates = VIEWPORT.scale(self.position * SCALE)
            return

        for e in entities:  # Iterate over all the entities to calculate physics
            if e == self or type(e) == Rocket:
                continue

            self.acceleration = calculate_force(self, e)

        self.velocity += self.acceleration * dt
        self.position += self.velocity * dt  # type: ignore
        self.acceleration = pg.Vector2(0, 0)

        temp = self.position * SCALE
        self.coordinates = VIEWPORT.scale(temp)
        if self.has_trail:
            self.trail.append(self.coordinates)
            self.trail_real.append(temp)

    def draw(self):
        self.coordinates = VIEWPORT.scale(self.position * SCALE)
        if self.has_trail:
            pg.draw.lines(SCREEN, self.color, False, self.trail)
        pg.draw.circle(SCREEN, self.color, self.coordinates, self.radius / VIEWPORT.scaling * SCALE)


class Rocket(Entity):
    def __init__(self, coordinates, init_velocity, radius, color, stage_masses, stage_fuel, stage_engine_thrust, stage='LEO', has_trail=True):
        super().__init__(coordinates, init_velocity, radius, stage_masses[0], color, has_trail)
        '''
        stage names are:
        LEO - low Earth orbit
        GTO - geosynchronous transfer orbit or geostationary transfer orbit
        HEO - heliocentric orbit
        '''
        self.stage = stage
        self.stage_masses = stage_masses

    def move(self, directions):
        # TODO fix
        if self.velocity.length() > MAX_ROCKET_VELOCITY:
            return

        self.acceleration = pg.Vector2(0, 0)
        for e in directions:
            self.acceleration += e

        dx = self.acceleration.x
        dy = self.acceleration.y
        if abs(dx) == abs(dy) == 1:  # Check for diagonal movement
            self.acceleration.x = 1/2**0.5 * dx
            self.acceleration.y = 1/2**0.5 * dy

        self.acceleration *= ROCKET_ACCEL


class Planet(Entity):
    def __init__(self, coordinates, init_velocity, radius, mass, color, has_trail=True):
        super().__init__(coordinates, init_velocity, radius, mass, color, has_trail)


class PlanetStatic(Planet):
    def __init__(self, coordinates, radius, mass, color, has_trail=True):
        super().__init__(coordinates, pg.Vector2(0, 0), radius, mass, color, has_trail)


class OnScreenText:
    def __init__(self, text, fontsize, coords, antial=True, center=True, color=(0, 0, 0)):
        self.text = text
        self.fontsize = fontsize
        self.color = color
        self.antial = antial
        self.coords = coords
        self.center = center

        self.rendered_text = self.fontsize.render(self.text, self.antial, self.color)
        if self.center == True:
            self.rect = self.rendered_text.get_rect(center=self.coords)
        else:
            self.rect = coords

    def blit(self):
        SCREEN.blit(self.rendered_text, self.rect)

    def update(self, text):
        self.text = text
        self.rendered_text = self.fontsize.render(self.text, self.antial, self.color)
        if self.center == True:
            self.rect = self.rendered_text.get_rect(center=self.coords)
        else:
            self.rect = self.coords


class Button:
    def __init__(self, color, x, y, width, height, text=""):
        self.color = color
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.text = text

    def draw(self, outline=None):
        if outline:
            pg.draw.rect(SCREEN, outline, (self.x + 5, self.y + 5, self.width, self.height), 0)
        pg.draw.rect(SCREEN, self.color, (self.x, self.y, self.width, self.height), 0)

        if self.text != "":
            lines = self.text.split("\n")
            for i, line in enumerate(lines, start=1):
                text = FONTS.render(line, True, (255, 255, 255))

                SCREEN.blit(
                    text,
                    (self.x + (self.width/2 - text.get_width()/2),
                     self.y + (self.height/(len(lines) + 1) * i - text.get_height()/2))
                )

    def is_over(self, pos):
        if self.x < pos[0] < self.x + self.width:
            if self.y < pos[1] < self.y + self.height:
                return True
        return False


# Checks if e1 collides with e2 and changes its parameters
def calculate_collision(e1, e2, d):
    r1 = e1.radius
    r2 = e2.radius

    if type(e1) == Rocket:
        e1.velocity = e2.velocity
        e1.position = e2.position + d
        if d.length() <= r1 + r2:
            e1.acceleration = pg.Vector2(0, 0)
    elif type(e2) == Rocket:
        return
    elif e1.mass < e2.mass:
        e1.velocity = e2.velocity
        e1.position = e2.position
    # TODO handle this case
    # elif e1.mass == e2.mass:
    #     pass
    else:
        e2.velocity = e1.velocity
        e2.position = e1.position


# Changes the acceleration of entity1
def calculate_force(e1, e2):
    d = e1.position - e2.position
    r = e1.position.distance_to(e2.position)
    a = e1.acceleration

    if r < e1.radius + e2.radius + EPS:
        calculate_collision(e1, e2, d)
    else:
        f = d * (-G * e2.mass / (r * r * r))
        a += f
    return a


# Show planet info on LMB
def show_info():
    global SHOWING_INFO
    to_show = None
    max_distance = INFO_DISTANCE
    for e in entities:
        current_distance = e.coordinates.distance_to(event.pos)
        if current_distance < max_distance:
            max_distance = current_distance
            to_show = e
    
    if to_show == None:
        return
    
    SHOWING_INFO = to_show


# Basically handles any input, related to pygame events (except Rocket controls)
def event_handler(event):
    global VIEWPORT
    global LAUNCH_FROM
    global LMB_MODE

    match event.type:
        case pg.QUIT:
            sys.exit()
        case pg.KEYDOWN:
            match event.key:
                case pg.K_ESCAPE:
                    sys.exit()
                case pg.K_SPACE:
                    if SPEED_SLIDER.value != 0:
                        SPEED_SLIDER.value = 0
                    else:
                        SPEED_SLIDER.value = BASE_SPEED
                case pg.K_s:
                    VIEWPORT.shift = pg.Vector2(0, 0)
                    VIEWPORT.update(0)
                case pg.K_l:
                    LMB_MODE = "l"
                case pg.K_i:
                    LMB_MODE = "i"
        case pg.MOUSEBUTTONDOWN:
            match event.button:
                case 1:  # LMB to view info of the nearest entity
                    show_info()
                case 3:  # RMB to move view
                    VIEWPORT.shifting = True
                case 4:  # Scroll up to get closer to the Earth
                    VIEWPORT.update(-1)
                case 5:  # Scroll down to get further from the Earth
                    VIEWPORT.update(1)
        case pg.MOUSEBUTTONUP:
            match event.button:
                case 3:  # Release RMB to stop moving
                    VIEWPORT.shifting = False
        case pg.MOUSEMOTION:
            if VIEWPORT.shifting:
                VIEWPORT.shift += event.rel
                VIEWPORT.update(0)


pg.init()

# * Application options
CWD = os.path.dirname(__file__)
RES_PATH = os.path.join(CWD, "resources")
FONT_PATH = os.path.join(RES_PATH, "fonts")
IMG_PATH = os.path.join(RES_PATH, "images")

hp = "HPSimplified_Rg.ttf"
microgramma = "microgramma.ttf"

font = microgramma

FONTS = pg.font.Font((os.path.join(FONT_PATH, font)), 40)
FONTM = pg.font.Font((os.path.join(FONT_PATH, font)), 90)
FONTL = pg.font.Font((os.path.join(FONT_PATH, font)), 120)

RESOLUTION = W, H = (1500, 900)
SCREEN = pg.display.set_mode(RESOLUTION)
SCREEN_SURF = pg.Surface(RESOLUTION)
ICON = pg.image.load(os.path.join(IMG_PATH, "icon.png"))
pg.display.set_icon(ICON)

CLOCK = pg.time.Clock()
TIMER = time.time()
elapsed_time = time.time() - TIMER
etime_ost = OnScreenText(str(elapsed_time), FONTS, (W/2, H - 25), color=(240, 240, 250))

BG_COLOR = (0, 3, 10)

# * Interaction with application options
MOVE_MAP = {pg.K_UP:    pg.Vector2(0, -1),
            pg.K_DOWN:  pg.Vector2(0,  1),
            pg.K_LEFT:  pg.Vector2(-1, 0),
            pg.K_RIGHT: pg.Vector2(1,  0)}

INFO_DISTANCE = 20
SHOWING_INFO = None

INIT_SCALING = 0.1
INIT_SHIFT = pg.Vector2(-400, 0)
VIEWPORT = Viewport()

# Max amount of points trail has 
TRAILSIZE = 100

# * Physics 
# whole earth orbit in 156 seconds by moon if SPEED = 36
# to have real life time speed, you need to set BASE_SPEED to 9.584e-4 => 27d 7h 43m (5,859,780 seconds)
# the lower the speed, the more accurate the result, speed changes how often calculations happen
BASE_SPEED = 9.584e-4 #* 100 # <- it runs x100 faster, than it would in real life
SPEED = BASE_SPEED
SPEED_SLIDER = Slider(SCREEN, 20, 50, 8, H - 100,
                      min=BASE_SPEED, max=100, step=1, initial=BASE_SPEED,
                      vertical=True, colour=(255, 255, 255), handleColour=(255, 150, 30))

SCALE = 1/1000000
G = 6.67e-11
EPS = 1e3

# TODO Needs tweaking and rethinking
ROCKET_ACCEL = 7
# MAX_ROCKET_VELOCITY = 11200
MAX_ROCKET_VELOCITY = 11200e10

EARTH = PlanetStatic((W/2, H/2), 6371 * 1000, 5.972e24, (100, 100, 255))
MOON = PlanetStatic((W/2 + 405, H/2), 1737 * 1000, 7.347e22, (200, 200, 200))

ROCKET_RADIUS = 50
STARTING_POSITION = (EARTH.coordinates[0] - (EARTH.radius * SCALE + ROCKET_RADIUS * SCALE), EARTH.coordinates[1])
# masses including fuel, payload, etc.
STAGE_MASSES = [241_000, 65_000, 15_000]
# fuel mass
STAGE_FUEL = [171_800, 32_600, 12_375]
# thrust performance in vacuum without additional mass
STAGE_ENGINES_SPEED = [4 * 816.3, 1 * 816.3 + 4 * 47.1, 2 * 78.45]
# STAGE_MAX_THRUST = []

ROCKET = Rocket(STARTING_POSITION, (0, 0), ROCKET_RADIUS, (255, 100, 255), STAGE_MASSES, STAGE_FUEL, STAGE_ENGINES_SPEED)

entities = [EARTH, MOON, ROCKET]
VIEWPORT.update(0)

while True:
    CLOCK.tick(60)

    dt = CLOCK.tick(60) * SPEED_SLIDER.value

    events = pg.event.get()
    for event in events:
        event_handler(event)

    SCREEN_SURF.fill(BG_COLOR)
    SCREEN.blit(SCREEN_SURF, (0, 0))

    if dt != 0:
        pressed = pg.key.get_pressed()
        ROCKET.move([MOVE_MAP[key] for key in MOVE_MAP if pressed[key]])

        for e in entities:
            e.update()

    for e in entities:
        e.draw()
    ROCKET.draw()

    elapsed_time = time.time() - TIMER
    etime_ost.update(f'{str(elapsed_time).split(".")[0]}.{str(elapsed_time).split(".")[1][:3]}')
    etime_ost.blit()

    pw.update(events)
    pg.display.update()
