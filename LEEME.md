# word_com — automatización de Word para evaluación independiente de seguridad

Módulo de Python que pilota el Microsoft Word instalado mediante COM (pywin32)
para revisar documentación técnica ferroviaria entre versiones sucesivas.

A diferencia de las bibliotecas que manipulan el XML del `.docx` (python-docx),
aquí las operaciones las ejecuta el propio Word: se conserva íntegramente el
formato (tablas anidadas, campos, numeración automática, índices, referencias
cruzadas) y se dispone de la **paginación real**.

## Requisitos

* Windows con Microsoft Word instalado.
* `pip install pywin32`
* `pip install openpyxl` (opcional; sin él las tablas se exportan a CSV).

## Comprobación inicial

```
python ejemplo_uso.py diagnostico
```

Arranca Word, muestra la versión instalada y lo cierra. Conviene ejecutarlo
antes de procesar documentos reales.

## Funcionalidades

| Orden | Función |
|---|---|
| `comparar` | Compara dos versiones y genera un `.docx` con las diferencias marcadas, más un Excel de diferencias |
| `comentarios` | Extrae los comentarios (autor, fecha, página, texto comentado) a Excel |
| `cambios` | Extrae los cambios registrados (control de cambios) a Excel |
| `campos` | Actualiza campos, índices y referencias cruzadas, y guarda una copia |
| `pdf` | Exporta a PDF con la paginación real, con o sin marcas de revisión |
| `lote-comparar` | Compara todos los pares de versiones `_vNN` de una carpeta |
| `lote-comentarios` | Extrae los comentarios de todos los documentos de una carpeta |

Ejemplo:

```
python ejemplo_uso.py lote-comparar "\\servidor\proyectos\LAV" ^
    --salida "C:\Trabajo\Comparativas"
```

## Garantías de funcionamiento

* **El documento original nunca se modifica.** Toda operación de escritura
  trabaja sobre una copia local en una carpeta temporal, que se elimina al
  terminar. Los originales se abren además en modo de sólo lectura.
* **No quedan procesos colgados.** La sesión de Word es un gestor de contexto
  con bloques `finally`: aunque el script falle o se interrumpa, se cierran los
  documentos y termina el proceso `WINWORD.EXE`. Si el cierre ordenado no
  responde, se fuerza la terminación del PID de esa sesión (nunca la de otras
  instancias de Word abiertas por el usuario).
* **Instancia dedicada.** Se emplea `DispatchEx`, no `Dispatch`: el script
  arranca su propio proceso de Word y no interfiere con el Word en el que el
  usuario esté trabajando.
* **Un documento defectuoso no aborta el lote.** Los documentos protegidos,
  bloqueados por otro proceso o dañados se registran como incidencia y el
  proceso continúa con los restantes.

## Notas de uso

* **Rutas.** Se recomienda usar rutas UNC (`\\servidor\recurso\...`) en lugar
  de la letra de unidad asignada (`Y:`), porque las unidades asignadas sólo
  existen en la sesión del usuario que las asignó. El módulo convierte en todo
  caso las rutas a absolutas: Word resuelve las rutas relativas contra su
  propio directorio de trabajo, no contra el de Python.
* **Vista Protegida.** Los documentos procedentes de ubicaciones de red pueden
  abrirse en Vista Protegida, lo que impide editarlos y compararlos. Como todas
  las operaciones de escritura se realizan sobre una copia local, el problema
  queda resuelto.
* **Emparejamiento de versiones.** Se detecta el sufijo `_vNN` al final del
  nombre (`PROY_Senalizacion_v03.docx`). Los ficheros sin ese sufijo y los
  temporales de bloqueo (`~$...`) se omiten.
* **Cambios pendientes.** Si un documento llega con control de cambios sin
  aceptar, se deja constancia en el registro: Word los considera aceptados al
  comparar.

## Constantes de Word

Las constantes numéricas (`wdFormatPDF = 17`, `wdCompareTargetNew = 2`, etc.)
están agrupadas en la clase `Wd` de `word_com.py`, con los nombres originales de
VBA para poder localizarlas en la documentación de Microsoft Learn o en el
Examinador de objetos del editor VBA de Word (Alt+F11, luego F2).
