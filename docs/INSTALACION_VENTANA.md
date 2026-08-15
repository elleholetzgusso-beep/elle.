# Versión con ventana (Tkinter) — notas de instalación

## Qué hay en esta carpeta

- `interfaz.py` — la ventana. Sustituye el menú de consola de `lanzador.py`.
  Usa el mismo motor (`organizador/`): no cambia ninguna lógica de creación,
  organización, historial ni deshacer.
- `Organizador_Exceltic_Ventana.bat` — lo que abre Roberto (doble clic o
  arrastrar una carpeta encima). Si el equipo no puede abrir la ventana,
  cae automáticamente al menú de consola de siempre.
- `Preparar_Tkinter.bat` — se ejecuta **una sola vez**, desde un PC que tenga
  Python instalado: copia Tkinter dentro de `python-embed` de forma automática
  (ver el aviso más abajo). No necesita permisos de administrador.
- `assets/` (opcional) — `logo-mark.png` y `logo-lockup.png`. Si están, la
  ventana muestra el logo real; si no, muestra el nombre en texto.

## Dónde copiar

Copia estos archivos **dentro de la misma carpeta** donde ya viven
`lanzador.py`, `organizador/` y `python-embed/`:

```
Y:\Herramientas\OrganizadorExceltic\
├── organizador\
├── python-embed\
├── lanzador.py                       (menú de consola, se mantiene)
├── interfaz.py                       ← nuevo
├── Organizador_Exceltic.bat          (consola, se mantiene)
├── Organizador_Exceltic_Ventana.bat  ← nuevo, el que usa Roberto
├── Preparar_Tkinter.bat              ← nuevo, se ejecuta una sola vez
└── assets\logo-mark.png, logo-lockup.png   ← opcional
```

## Aviso importante: el Python embeddable NO trae Tkinter

El paquete *embeddable* de python.org viene sin Tkinter (sin `tkinter/`,
sin `_tkinter.pyd`, sin `tcl/`), así que **la ventana no arranca con
`python-embed` tal como está hoy**. Tres salidas, de la más simple a la
menos:

1. **Completar `python-embed` con Tkinter** (recomendado). Instala Python 3.12
   desde python.org en tu propio PC (dejando marcada la opción *tcl/tk and
   IDLE*) y ejecuta **`Preparar_Tkinter.bat`** desde la carpeta de red: busca
   el Python instalado, copia lo que falta (`_tkinter.pyd`, `tcl86t.dll`,
   `tk86t.dll`, `zlib1.dll`, `Lib\tkinter\`, `tcl\`), añade `tcl` al `._pth`
   y comprueba al final que la ventana ya arranca. Se hace una sola vez;
   después el equipo de Roberto no necesita instalar nada ni tener permisos
   de administrador.

2. **`.exe` con PyInstaller** — `pyinstaller --onedir --windowed --noupx
   --clean --name OrganizadorExceltic interfaz.py`. PyInstaller sí empaqueta
   Tkinter. Ojo con los falsos positivos de antivírus (ver README principal);
   distribuir la carpeta entera por la unidad de red, nunca por correo.

3. **No hacer nada** — el `.bat` detecta que falta Tkinter y abre el menú de
   consola. Funcional, pero sin la parte visual.

## Comprobaciones antes de entregar

- [ ] Ejecutar `Preparar_Tkinter.bat` una vez y ver el mensaje "Listo".

- [ ] Abrir el `.bat` con doble clic: la ventana aparece, sin consola detrás.
- [ ] Arrastrar una carpeta sobre el `.bat`: la ruta ya viene rellenada.
- [ ] Las cuatro operaciones, siempre con previsualización antes de aplicar.
- [ ] Aplicar y luego Deshacer desde el historial.
- [ ] Carpeta inexistente / sin permiso de escritura: mensaje en español,
      la ventana no se cierra.
- [ ] Error inesperado: se escribe el `.txt` de log y los botones "Abrir
      carpeta" y "Copiar ruta" funcionan.
- [ ] Probar en un equipo sin Python instalado, accediendo por `Y:\`.
