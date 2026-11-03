# E17 ? Estado y continuaci?n (2026-11-03)

## Estado actual

- KaliTagRoles v0.4.5: roles y grupos almacenados en atributos, sin leer ni
  escribir Description. Se elimin? el cuello de botella de 282.4 s en 154
  escrituras de descripci?n; el usuario confirm? la ejecuci?n r?pida.
- Filler_Door / Filler_Doors siguen el acabado de puertas; Filler_Carcass y sus
  variantes siguen carcasa mediante KFS_RENDER/finish_target. El rol sigue FILLER.
- CounterTop_Fascia y Front_border: COUNTERTOP_FASCIA, acabado de encimera.
- Profile_upper_nail, Profile_upper_base, Profile_base y Profile_nail:
  GOLA_PROFILE. Back_side: CARCASS_PANEL; Panel_door_lower: DOOR.
- KaliExportRender v0.1.5: exporta finish_target y excluye KitchenBar/Body1 por
  confirmaci?n expresa del operador, independientemente de su visibilidad.
  Exclusi?n espec?fica del template, registrada como BODY_EXCLUDED; no se borra
  el cuerpo de Fusion. La regla se prob? con cuerpos visibles, ocultos y otros
  nombres de componente. Falta ejecutar v0.1.5 en Fusion para validarla all?.
- Gateway: importaci?n, renders perspectiva/frontal/interior, accesorios propios,
  exportaci?n GLB con/sin paredes y visor local con giro, zoom y auto rotaci?n.
- Studio: /visualization-preview protegido por autenticaci?n, selector GLB local
  sin subida, estados de carga/error y limpieza de object URLs. Implementado en
  rama, no desplegado ni integrado con almacenamiento/revisiones de proyectos.

## ?ltima validaci?n real

Paquete fuente del 2026-11-02 a las 21:43:30, exportador v0.1.4:
162 mallas, 259 instancias, 196 cuerpos importados y 196 controles dimensionales
independientes contra Fusion. No quedaron piezas con geometr?a sin rol.
Se generaron tres renders, una vista elevada de la esquina y dos GLB.
El GLB incluy? 181 cuerpos fuente visibles; la reimportaci?n verific? identidad,
materiales y coordenadas con error m?ximo medido de 0 mm. La geometr?a de la
escena fuente no cambi?. Modelos, im?genes y reportes se mantienen locales.
El fallo de ese paquete sigue siendo KitchenBar/Body1 (previo a la correcci?n
v0.1.5); no afirmar que una exportaci?n real con esa versi?n ya pas?.

## Pendiente inmediato: gola oculta

El usuario detect? franjas blancas en el visor. Los diez Profile_* s? recibieron
BLACK_MATTE, pero ambos grupos Gola y sus descendientes llegaron con
source_visibility=false y render_enabled=false. No es un material blanco
asignado al perfil: el perfil no se est? mostrando. No forzar su visibilidad
silenciosamente en Blender ni recolorear la carcasa para ocultar el problema.

1. Activar Gola y sus descendientes en GBC01 y GBC02 en Fusion.
2. Guardar los dise?os y actualizar las inserciones vinculadas en la cocina.
3. Exportar con v0.1.5; comprobar perfiles visibles y BODY_EXCLUDED sin fallo
   de tessellaci?n para el auxiliar KitchenBar/Body1.
4. Regenerar im?genes y visor; revisar franjas negras con el operador.

## Trabajo posterior

- Ajustes de muebles en Fusion por el usuario y validaci?n con segunda cocina.
- Cat?logos/muestras reales de proveedores locales. Verde olivo, negro mate,
  blanco y pared perla/beige son una paleta ilustrativa aprobada visualmente,
  no SKUs calibrados ni aprobaci?n de fabricaci?n.
- Automatizar el flujo completo con un comando reutilizable; la orquestaci?n
  usada para estas pruebas a?n es local. Agente en espa?ol despu?s del flujo
  determinista; no hay endpoint de trabajos ni publicaci?n de resultados.
- Identidades actuales son de snapshot, no estables entre exportaciones.
- Mantener mm en Fusion/paquete y metros en Blender/GLB; Y-up de Fusion se
  convierte a Z-up en Blender y a Y-up en glTF una sola vez por frontera.
