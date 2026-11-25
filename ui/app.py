from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from core.world import World
from loaders import (
    build_world,
    creature_from_program,
    load_creatures_from_dir,
    load_objects_from_dir,
    load_terrains_from_dir,
    parse_map_file,
)
from lang.simulation import Simulation


CELL_SIZE = 32

TERRAIN_COLORS = {
    "Grass": "#A8E6A3",
    "Water": "#7EC8E3",
    "Lava": "#FF6B35",
    "Sand": "#F4D58D",
    "Stone": "#A0A0A0",
}
FALLBACK_TERRAIN_COLORS = [
    "#D4E6D4", "#E6D4D4", "#D4D4E6", "#E6E6D4",
    "#E0C0E0", "#C0E0E0", "#E0E0C0", "#C0C0E0",
]
FACTION_COLORS = [
    "#FF5555", "#5555FF", "#55AA55", "#AA55AA",
    "#FFAA00", "#00AAAA", "#AA0000", "#00AA00",
]

def _stable_hash(s: str) -> int:
    h = 0
    for ch in s:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return h

def terrain_color(name: str) -> str:
    if name in TERRAIN_COLORS:
        return TERRAIN_COLORS[name]
    return FALLBACK_TERRAIN_COLORS[_stable_hash(name) % len(FALLBACK_TERRAIN_COLORS)]

def faction_color(faction: str) -> str:
    return FACTION_COLORS[_stable_hash(faction) % len(FACTION_COLORS)]

class InstinctApp:
    def __init__(self, root: tk.Tk, data_dir: Path) -> None:
        self.root = root
        self.data_dir = data_dir

        # Datos cargados
        self.terrains: dict = {}
        self.objects: dict = {}
        self.map_data: dict = {}
        self.creatures: dict = {}

        # Estado de simulacion
        self.world: World | None = None
        self.simulation: Simulation | None = None
        self.selected_map: str | None = None
        self.selected_species: str | None = None
        self.placements: list[tuple[str, int, int]] = []

        # Estado de la UI
        self.phase = "setup"  # setup | running | paused
        self.speed_ms = 100
        self.after_id: str | None = None
        self._world_log_shown = 0

        root.title("Instinct Simulator")
        root.geometry("1150x700")

        self._build_ui()
        self._load_data()
        self._populate_lists()
        self._bind_shortcuts()

    # -------------- construccion de la UI --------------

    def _build_ui(self) -> None:
        toolbar = ttk.Frame(self.root, padding=5)
        toolbar.pack(side="top", fill="x")

        ttk.Label(toolbar, text="Mapa:").pack(side="left", padx=(0, 4))
        self.map_combo = ttk.Combobox(toolbar, state="readonly", width=18)
        self.map_combo.pack(side="left", padx=(0, 12))
        self.map_combo.bind("<<ComboboxSelected>>", self._on_map_selected)

        ttk.Label(toolbar, text="Criatura:").pack(side="left", padx=(0, 4))
        self.species_combo = ttk.Combobox(toolbar, state="readonly", width=14)
        self.species_combo.pack(side="left", padx=(0, 12))
        self.species_combo.bind("<<ComboboxSelected>>", self._on_species_selected)

        ttk.Label(toolbar, text="Modo:").pack(side="left", padx=(0, 4))
        self.mode_var = tk.StringVar(value="place")
        ttk.Radiobutton(toolbar, text="Colocar", variable=self.mode_var,
                        value="place").pack(side="left")
        ttk.Radiobutton(toolbar, text="Eliminar", variable=self.mode_var,
                        value="remove").pack(side="left", padx=(0, 12))

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)

        self.play_btn = ttk.Button(toolbar, text="▶ Play", command=self._play)
        self.play_btn.pack(side="left", padx=2)
        self.pause_btn = ttk.Button(toolbar, text="⏸ Pausa", command=self._pause,
                                     state="disabled")
        self.pause_btn.pack(side="left", padx=2)
        self.step_btn = ttk.Button(toolbar, text="⏭ Paso", command=self._step,
                                    state="disabled")
        self.step_btn.pack(side="left", padx=2)
        self.reset_btn = ttk.Button(toolbar, text="⟳ Reset", command=self._reset)
        self.reset_btn.pack(side="left", padx=2)

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)

        ttk.Label(toolbar, text="Velocidad:").pack(side="left", padx=(0, 4))
        for label, ms in (("Lenta", 500), ("Normal", 100), ("Rápida", 33)):
            ttk.Button(
                toolbar, text=label,
                command=lambda m=ms: self._set_speed(m),
            ).pack(side="left", padx=2)

        center = ttk.Frame(self.root, padding=5)
        center.pack(side="top", fill="both", expand=True)

        self.canvas = tk.Canvas(center, bg="white", highlightthickness=1,
                                highlightbackground="gray")
        self.canvas.pack(side="left", fill="both", expand=True, padx=(0, 5))
        self.canvas.bind("<Button-1>", self._on_canvas_click)

        log_frame = ttk.LabelFrame(center, text="Logs", padding=2)
        log_frame.pack(side="right", fill="y")

        self.log_text = tk.Text(log_frame, width=40, state="disabled",
                                wrap="word", font=("Consolas", 9))
        self.log_text.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scroll.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=scroll.set)

        self.status_var = tk.StringVar(value="Listo. Carga un mapa para empezar.")
        ttk.Label(self.root, textvariable=self.status_var,
                  relief="sunken", anchor="w", padding=3).pack(side="bottom", fill="x")

    def _bind_shortcuts(self) -> None:
        self.root.bind("<space>", lambda e: (
            self._pause() if self.phase == "running" else self._play()
        ))
        self.root.bind("<r>", lambda e: self._reset())
        self.root.bind("<s>", lambda e: self._step())

    # --------------- carga de datos -----------------------

    def _load_data(self) -> None:
        self.terrains, e1 = load_terrains_from_dir(self.data_dir / "terrains")
        self.objects, e2 = load_objects_from_dir(
            self.data_dir / "objects", self.terrains
        )
        self.creatures, e3 = load_creatures_from_dir(self.data_dir / "creatures")

        maps_dir = self.data_dir / "maps"
        errors = list(e1 + e2 + e3)
        if maps_dir.is_dir():
            for path in sorted(maps_dir.glob("*.map")):
                try:
                    md = parse_map_file(path)
                except Exception as e:
                    errors.append(e)
                    continue
                if md.name in self.map_data:
                    errors.append(f"{path}: mapa duplicado {md.name!r}")
                    continue
                self.map_data[md.name] = md
        else:
            errors.append(f"{maps_dir}: directorio no existe")

        for e in errors:
            self._log(f"ERROR: {e}")
        self._log(
            f"Cargados: {len(self.terrains)} terrenos, "
            f"{len(self.objects)} objetos, "
            f"{len(self.map_data)} mapas, "
            f"{len(self.creatures)} criaturas."
        )

    def _populate_lists(self) -> None:
        maps = sorted(self.map_data.keys())
        self.map_combo["values"] = maps
        if maps:
            self.map_combo.current(0)
            self._on_map_selected(None)

        species = sorted(self.creatures.keys())
        self.species_combo["values"] = species
        if species:
            self.species_combo.current(0)
            self._on_species_selected(None)

    # -------------------- eventos de la barra ----------------------

    def _on_map_selected(self, event) -> None:
        if self.phase == "running":
            self.map_combo.set(self.selected_map or "")
            return
        name = self.map_combo.get()
        if not name:
            return
        self.selected_map = name
        md = self.map_data[name]
        try:
            self.world = build_world(md, self.terrains, self.objects)
        except Exception as e:
            self._log(f"Error construyendo mundo: {e}")
            self.world = None
            return
        self.simulation = Simulation(self.world, seed=42)
        self.placements.clear()
        self._world_log_shown = 0
        self.phase = "setup"
        self._apply_phase()
        self._resize_canvas()
        self._draw()
        self._update_status()
        self._log(f"Mapa '{name}' cargado ({md.width}x{md.height}).")

    def _on_species_selected(self, event) -> None:
        name = self.species_combo.get()
        if name:
            self.selected_species = name

    def _on_canvas_click(self, event) -> None:
        if self.world is None or self.phase != "setup":
            return
        x = event.x // CELL_SIZE
        y = event.y // CELL_SIZE
        if not self.world.is_inside(x, y):
            return

        if self.mode_var.get() == "place":
            if not self.selected_species:
                self._log("Selecciona una especie primero.")
                return
            program = self.creatures.get(self.selected_species)
            if program is None:
                return
            creature = creature_from_program(program)
            if not self.world.place_creature(creature, x, y):
                self._log(f"No se puede colocar en ({x},{y}): ocupada o fuera del mapa.")
                return
            self.placements.append((self.selected_species, x, y))
            self._log(f"Colocada {self.selected_species} en ({x},{y}).")
        else:
            creature = self.world.creature_at(x, y)
            if creature is None:
                return
            self.world.remove_creature(creature)
            try:
                self.placements.remove((creature.species, x, y))
            except ValueError:
                pass
            self._log(f"Eliminada {creature.species} de ({x},{y}).")

        self._draw()
        self._update_status()

    # ---------------------- fases ----------------------------------------

    def _apply_phase(self) -> None:
        states = {
            "setup":   ("normal", "disabled", "disabled"),
            "running": ("disabled", "normal", "disabled"),
            "paused":  ("normal", "disabled", "normal"),
        }
        play, pause, step = states[self.phase]
        self.play_btn.configure(state=play)
        self.pause_btn.configure(state=pause)
        self.step_btn.configure(state=step)

    def _play(self) -> None:
        if self.world is None:
            self._log("Carga un mapa primero.")
            return
        if self.phase == "running":
            return
        if not self.world.creatures:
            self._log("No hay criaturas en el mapa.")
            return
        self.phase = "running"
        self._apply_phase()
        self._schedule_tick()

    def _pause(self) -> None:
        if self.phase != "running":
            return
        self.phase = "paused"
        self._apply_phase()
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None

    def _step(self) -> None:
        if self.world is None or self.simulation is None:
            return
        if self.phase == "running":
            return
        self.simulation.step()
        self._draw()
        self._flush_world_logs()
        self._update_status()
        if not self.world.creatures:
            self._log("Todas las criaturas han muerto.")

    def _reset(self) -> None:
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None
        if self.selected_map is None:
            return
        md = self.map_data.get(self.selected_map)
        if md is None:
            return
        self.world = build_world(md, self.terrains, self.objects)
        for species, x, y in self.placements:
            program = self.creatures.get(species)
            if program is None:
                continue
            creature = creature_from_program(program)
            self.world.place_creature(creature, x, y)
        self.simulation = Simulation(self.world, seed=42)
        self._world_log_shown = 0
        self.phase = "setup"
        self._apply_phase()
        self._draw()
        self._update_status()
        self._log("Simulación reiniciada.")

    def _set_speed(self, ms: int) -> None:
        self.speed_ms = ms
        if self.phase == "running":
            if self.after_id is not None:
                self.root.after_cancel(self.after_id)
            self._schedule_tick()

    def _schedule_tick(self) -> None:
        self.after_id = self.root.after(self.speed_ms, self._tick)

    def _tick(self) -> None:
        self.after_id = None
        if self.phase != "running" or self.simulation is None or self.world is None:
            return
        self.simulation.step()
        self._draw()
        self._flush_world_logs()
        self._update_status()
        if not self.world.creatures:
            self.phase = "paused"
            self._apply_phase()
            self._log("Todas las criaturas han muerto.")
            return
        self._schedule_tick()

    # ----------------------- dibujo y estado --------------------

    def _resize_canvas(self) -> None:
        if self.world is None:
            return
        self.canvas.configure(
            width=self.world.width * CELL_SIZE,
            height=self.world.height * CELL_SIZE,
        )

    def _draw(self) -> None:
        self.canvas.delete("all")
        if self.world is None:
            return
        for y in range(self.world.height):
            for x in range(self.world.width):
                cell = self.world.get_cell(x, y)
                if cell is None:
                    continue
                x0 = x * CELL_SIZE
                y0 = y * CELL_SIZE
                x1 = x0 + CELL_SIZE
                y1 = y0 + CELL_SIZE

                self.canvas.create_rectangle(
                    x0, y0, x1, y1,
                    fill=terrain_color(cell.terrain.name),
                    outline="#888888",
                )

                if cell.world_object is not None:
                    self.canvas.create_text(
                        (x0 + x1) // 2, (y0 + y1) // 2,
                        text=cell.world_object.char,
                        fill="#333333",
                        font=("Consolas", 14, "bold"),
                    )
                elif cell.creature is not None:
                    c = cell.creature
                    pad = 4
                    self.canvas.create_oval(
                        x0 + pad, y0 + pad, x1 - pad, y1 - pad,
                        fill=faction_color(c.faction),
                        outline="#222222",
                    )
                    self.canvas.create_text(
                        (x0 + x1) // 2, (y0 + y1) // 2,
                        text=c.species[:1].upper(),
                        fill="white",
                        font=("Arial", 12, "bold"),
                    )

    def _flush_world_logs(self) -> None:
        if self.world is None:
            return
        for entry in self.world.log[self._world_log_shown:]:
            self._log(entry)
        self._world_log_shown = len(self.world.log)

    def _update_status(self) -> None:
        if self.world is None:
            self.status_var.set("Sin mapa cargado.")
            return
        self.status_var.set(
            f"Tick {self.world.tick_count} | "
            f"Criaturas: {len(self.world.creatures)} | "
            f"Fase: {self.phase} | "
            f"Mapa: {self.selected_map or '-'}"
        )

    def _log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")