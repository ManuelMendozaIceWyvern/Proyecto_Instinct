NONE = -1
GROUND = 0
OBJECT = 1
ALLY = 2
ENEMY = 3

CONSTANTS: dict[str, int] = {
    "NONE": NONE,
    "GROUND": GROUND,
    "OBJECT": OBJECT,
    "ALLY": ALLY,
    "ENEMY": ENEMY,
}

PERCEPTION_NAMES: set[str] = {
    # sobre si misma
    "health", "age", "lifespan", "vision", "species", "faction",
    "x", "y", "terrain_here", "reserve_here",

    # sobre el mundo
    "width", "height", "tick",
    "total_creatures", "total_allies", "total_enemies",
    "random",
    
    # sobre lo cercano
    "allies_near", "enemies_near", "objects_near",
    "enemy_dist", "enemy_dx", "enemy_dy",
    "ally_dist", "ally_dx", "ally_dy",
    "object_dist", "object_dx", "object_dy",
    "roars_near", "last_roar",
}