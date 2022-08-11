from typing import Sequence, Union
from typing_extensions import Self
import pygame as pg

CollisionLayer = Union[int, str]


class CollisionLayers:
    CAR: CollisionLayer = 0


class Constants:
    TILE_SIZE: int = 500


class Object(pg.sprite.Sprite):
    """
    Base class for entities and anything
    else that is present in the world.

    Collision layers can be integers or strings. Objects will only
    collide with objects they share at least one collision layer with.
    """

    rect: pg.rect.Rect
    image: pg.surface.Surface
    collision_layers: set[CollisionLayer]

    scale: Union[tuple[int, int], None]

    def __init__(
        self,
        pos: Union[tuple[int, int], pg.Vector2],
        collision_layers: set[CollisionLayer],
        img_path: Union[str, None] = None,
        world: Union["World", None] = None,
        scale: Union[tuple[int, int], int, None] = None,
    ):
        super().__init__()
        if scale is None or type(scale) is tuple:
            self.scale = scale
        elif type(scale) is int:
            self.scale = (scale, scale)
        else:
            raise TypeError(
                f"scale must be an int or tuple or None. Got {scale} ({type(scale)})"
            )

        if not img_path:
            if self.scale:
                self.image = pg.Surface(self.scale)
            else:
                self.image = pg.Surface((0, 0))
        else:
            self.image = pg.image.load(img_path)
            if self.scale:
                self.image = pg.transform.scale(self.image, self.scale)

        self.rect = self.image.get_rect()
        self.rect.topleft = int(pos[0]), int(pos[1])
        self.collision_layers = collision_layers

        if world:
            world.add_object(self)


class Tile(pg.sprite.Sprite):
    """
    A tile representing a segment of the world.
    Tiles are always the same square size (Constants.TILE_SIZE).
    It contains any objects in fixed positions.
    """

    image: pg.surface.Surface

    def __init__(
        self,
        img_path: Union[str, None] = None,
        colour: pg.color.Color = pg.Color("gray"),
    ) -> None:
        super().__init__()

        if img_path:
            self.image = pg.image.load(img_path)
            self.image = pg.transform.scale(
                self.image, (Constants.TILE_SIZE, Constants.TILE_SIZE)
            )
        else:
            self.image = pg.Surface((Constants.TILE_SIZE, Constants.TILE_SIZE))
            self.image.fill(colour)

    def update(self, tick: bool = False):
        pass


class Entity(Object):
    """
    An object with physics properties such as velocity and rotation.
    Since entities can be rotated, keeping an original_image is useful.

    true_pos is needed for entities to have sub-pixel positioning.

    Velocity is measured in units/tick.
    Angle is measured in degrees.
    Friction is measured in units/tick/tick.
    Mass is used in friction calculation.

    mask is used in collision detection. It is recalculated on rotation.
    """

    true_pos: pg.math.Vector2

    original_image: pg.surface.Surface

    velocity: pg.math.Vector2
    angle: float
    friction: float
    mass: float

    mask: pg.mask.Mask

    def __init__(
        self,
        pos: Union[tuple[int, int], pg.Vector2],
        collision_layers: set[CollisionLayer],
        img_path: Union[str, None] = None,
        scale: Union[tuple[int, int], int, None] = None,
    ):
        super().__init__(pos, collision_layers, img_path=img_path, scale=scale)

        self.true_pos = pg.Vector2(pos)

        self.original_image = self.image.copy()

        self.velocity = pg.math.Vector2(0, 0)
        self.angle = 0
        self.friction = 0.006
        self.mass = 1

        self.mask = pg.mask.from_surface(self.image)

    def update(self, tick: bool = False) -> None:
        super().update()

        if tick:

            # Apply velocity
            self.true_pos += self.velocity
            self.rect.center = int(self.true_pos[0]), int(self.true_pos[1])

            # Handle Friction
            if self.velocity.magnitude() and self.friction > 0:
                f = max(
                    self.friction * self.mass,
                    self.friction * self.mass * self.velocity.magnitude() / 3,
                )
                print(self.velocity.magnitude(), f)
                if abs(self.velocity.magnitude()) - f <= 0:
                    # If this tick of friction would make the entity move in the opposite direction, set velocity to 0.
                    self.velocity = pg.math.Vector2(0, 0)
                else:
                    self.accelerate(-f)

    def accelerate(self, magnitude: float) -> None:
        """
        Accelerate the entity in its current direction.
        """

        acceleration_vector = pg.math.Vector2(magnitude, 0).rotate(self.angle)

        self.velocity += acceleration_vector

    def brake(self, magnitude: float) -> None:

        if self.velocity.magnitude() > 0.00001:
            self.velocity.scale_to_length(max(0, self.velocity.length() - magnitude))
        else:
            self.velocity = pg.math.Vector2(0, 0)

    def turn(self, angle: float) -> None:
        """
        Turn the entity by the given angle.
        Update mask when turned
        """

        # TODO: Better
        if self.velocity.magnitude() > 0.00001:
            self.angle += angle
            self.velocity.rotate_ip(angle)
            self.image = pg.transform.rotate(self.original_image, -self.angle)
            self.rect.size = self.image.get_size()
            self.mask = pg.mask.from_surface(self.image)

    def collide_entity(self, other: Self) -> bool:
        """
        Check for collision with another entity.
        """

        # Check if they share a collision layer
        if self.collision_layers & other.collision_layers:
            # TODO: return collision normal
            return (
                self.mask.overlap(
                    other.mask,
                    (other.rect.left - self.rect.left, other.rect.top - self.rect.top),
                )
                is not None
            )
        return False


class ControlledCar(Entity):
    """
    A controlled car.
    Acceleration is measured in units/tick/tick to increase velocity by
    when accelerating.
    Brake is measured in units/tick/tick to decrease velocity by when braking.
    """

    acceleration: float = 0.06
    braking: float = 0.05
    handling: float = 4

    def __init__(
        self,
        pos: tuple[int, int],
        collision_layers: set[CollisionLayer] = {CollisionLayers.CAR},
        img_path: Union[str, None] = "assets/images/blue_car.png",
        scale: Union[tuple[int, int], int, None] = (50, 28),
    ):
        super().__init__(pos, collision_layers, img_path=img_path, scale=scale)
        self.friction = 0.02

    def update(self, tick: bool = False) -> None:
        super().update(tick)

        if tick:
            # Handle input
            keys = pg.key.get_pressed()

            if keys[pg.K_UP]:
                self.accelerate(self.acceleration)
            if keys[pg.K_DOWN]:
                self.brake(self.braking)
            if keys[pg.K_RIGHT]:
                self.turn(self.handling)
            if keys[pg.K_LEFT]:
                self.turn(-self.handling)


class NPCCar(Entity):
    """
    Used for cars that aren't controlled by the player.
    It has a fixed path which it follows.
    """

    path: Sequence[tuple[int, int]]


class World:
    """
    Contains attributes and functions related to all tiles,
    entities and other objects in a world.
    tile_array is a 2D array of Tile objects. [COLUMN][ROW]
    group_tiles is a pygame.sprite.Group of all Tile objects.
    group_entities is a pygame.sprite.Group of all Entity objects including the player entity.
    """

    # TODO: check if this group is needed
    group_tiles: pg.sprite.Group
    group_objects: pg.sprite.Group

    tile_array: list[list[Union[Tile, None]]]

    empty_tile: Tile = Tile(colour=pg.Color("red"))

    def __init__(self, world_size: tuple[int, int]):
        self.group_tiles = pg.sprite.Group()
        self.group_objects = pg.sprite.Group()

        self.tile_array = [
            [None for _ in range(world_size[1])] for _ in range(world_size[0])
        ]

    def update(self, tick: bool = False, redraw: bool = True):
        # Update all tiles, objects and entities
        self.group_tiles.update(tick)
        self.group_objects.update(tick)

        if redraw:
            self.redraw()

    def redraw(self):
        self.image = pg.Surface(
            (
                len(self.tile_array[0]) * Constants.TILE_SIZE,
                len(self.tile_array) * Constants.TILE_SIZE,
            )
        )
        for colindex, col in enumerate(self.tile_array):
            for rowindex, tile in enumerate(col):

                tile_img = tile.image if tile else self.empty_tile.image
                self.image.blit(
                    tile_img,
                    (
                        colindex * Constants.TILE_SIZE,
                        rowindex * Constants.TILE_SIZE,
                    ),
                )

        self.group_objects.draw(self.image)

    def add_object(self, obj: Object) -> None:
        self.group_objects.add(obj)

    def add_tile(self, tile: Tile, col: int, row: int) -> None:
        if col < 0 or row < 0:
            raise IndexError(f"Tile out of bounds: col:{col} row:{row}")
        else:
            # If this tile is out of bounds, extend the tile_array
            if row > len(self.tile_array[0]) - 1:
                for c in self.tile_array:
                    c += [None] * (row - len(self.tile_array[0]) + 1)

            if col > len(self.tile_array) - 1:
                for _ in range(col - len(self.tile_array) + 1):
                    self.tile_array.append([None] * len(self.tile_array[0]))

            self.group_tiles.add(tile)
            self.tile_array[col][row] = tile

        self.redraw()


class Camera:
    """
    The camera manages what is visible in the current frame.
    It renders Tiles, cars and other objects if they are on screen
    at their correct positions.
    If it has a focus_object, it will smoothly follow it.
    """

    world: World

    pos: pg.math.Vector2
    focus_object: Union[Object, None]
    smoothing: float

    def __init__(
        self,
        world: World,
        size: tuple[int, int],
        pos: pg.math.Vector2 = pg.Vector2(450, 300),
        focus_object: Union[Object, None] = None,
        smoothing: float = 0.1,
    ):
        super().__init__()
        self.world = world
        self.size = size
        self.pos = pos
        self.focus_object = focus_object
        self.smoothing = smoothing

    def update(self):
        if self.focus_object:
            # self.pos = self.focus_object.rect.center
            d = pg.Vector2(self.focus_object.rect.center) - self.pos
            self.pos += d * self.smoothing

    def get_frame(self):
        self.image = pg.Surface(self.size)
        rect = self.image.get_rect()
        rect.center = int(self.pos.x), int(self.pos.y)
        self.image.blit(self.world.image, (0, 0), rect)
        return self.image


if __name__ == "__main__":
    pg.init()

    WIN = pg.display.set_mode((700, 500), pg.RESIZABLE)

    TILE_SIZE = 100  # Tile size in pixels

    world = World((5, 5))
    world.add_tile(Tile(img_path="assets/maps/dev/00.png"), 0, 0)
    world.add_tile(Tile(img_path="assets/maps/dev/01.png"), 0, 1)
    world.add_tile(Tile(img_path="assets/maps/dev/10.png"), 1, 0)
    world.add_tile(Tile(img_path="assets/maps/dev/11.png"), 1, 1)
    world.add_tile(Tile(img_path="assets/maps/dev/20.png"), 2, 0)

    player_car = ControlledCar((100, 100))
    world.add_object(player_car)

    camera = Camera(
        world, size=(700, 500), pos=pg.Vector2(100, 100), focus_object=player_car
    )

    CLOCK = pg.time.Clock()
    TPS = 60
    tst = 0  # time since tick

    # GAME LOOP
    while True:
        CLOCK.tick(60)

        # Determine whether a game tick is performed this frame
        tst += CLOCK.get_time()
        if tst >= 1000 / TPS:
            tick = True
        else:
            tick = False

        for event in pg.event.get():
            if event.type == pg.QUIT:
                pg.quit()
                quit()
            if event.type == pg.VIDEORESIZE:
                camera.size = event.size

        world.update(tick)
        camera.update()
        WIN.blit(camera.get_frame(), (0, 0))

        pg.display.flip()
