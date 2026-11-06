Current operator acceptance (2026-11-05): [pilot-acceptance.md](pilot-acceptance.md). The following status notes are historical.

# E17 — Estado y continuación (2026-11-03)

## Estado actual

Actualización 2026-11-05: el bloque blanco que ocultaba la esquina en PNG era
el cubo inicial de Blender, identificado mediante ray casting. El GLB ya lo
excluía. El renderer ahora usa una escena independiente con solo la colección
fuente y accesorios/setup propios; conserva la escena original y verifica
pertenencia antes de renderizar. La imagen elevada corregida muestra el rincón
sin ese bloque y mantiene intacta la geometría fuente. La explicación anterior
de que se debía únicamente a la cámara era incorrecta.

- KaliTagRoles v0.4.5: roles y grupos almacenados en atributos, sin leer ni
  escribir Description. Se eliminó el cuello de botella de 282.4 s en 154
  escrituras de descripción; el usuario confirmó la ejecución rápida.
- Filler_Door / Filler_Doors siguen el acabado de puertas; Filler_Carcass y sus
  variantes siguen carcasa mediante KFS_RENDER/finish_target. El rol sigue FILLER.
- CounterTop_Fascia y Front_border: COUNTERTOP_FASCIA, acabado de encimera.
- Profile_upper_nail, Profile_upper_base, Profile_base y Profile_nail:
  GOLA_PROFILE. Back_side: CARCASS_PANEL; Panel_door_lower: DOOR.
- KaliExportRender v0.1.5: exporta finish_target y excluye KitchenBar/Body1 por
  confirmación expresa del operador, independientemente de su visibilidad.
  Exclusión específica del template, registrada como BODY_EXCLUDED; no se borra
  el cuerpo de Fusion. La regla se probó con cuerpos visibles, ocultos y otros
  nombres de componente. Falta ejecutar v0.1.5 en Fusion para validarla allí.
- Gateway: importación, renders perspectiva/frontal/interior, accesorios propios,
  exportación GLB con/sin paredes y visor local con giro, zoom y auto rotación.
- Studio: /visualization-preview protegido por autenticación, selector GLB local
  sin subida, estados de carga/error y limpieza de object URLs. Implementado en
  rama, no desplegado ni integrado con almacenamiento/revisiones de proyectos.

## Última validación real

Paquete fuente del 2026-11-02 a las 21:43:30, exportador v0.1.4:
162 mallas, 259 instancias, 196 cuerpos importados y 196 controles dimensionales
independientes contra Fusion. No quedaron piezas con geometría sin rol.
Se generaron tres renders, una vista elevada de la esquina y dos GLB.
El GLB incluyó 181 cuerpos fuente visibles; la reimportación verificó identidad,
materiales y coordenadas con error máximo medido de 0 mm. La geometría de la
escena fuente no cambió. Modelos, imágenes y reportes se mantienen locales.
El fallo de ese paquete sigue siendo KitchenBar/Body1 (previo a la corrección
v0.1.5); no afirmar que una exportación real con esa versión ya pasó.

## Pendiente inmediato: gola oculta

El usuario detectó franjas blancas en el visor. Los diez Profile_* sí recibieron
BLACK_MATTE, pero ambos grupos Gola y sus descendientes llegaron con
source_visibility=false y render_enabled=false. No es un material blanco
asignado al perfil: el perfil no se está mostrando. No forzar su visibilidad
silenciosamente en Blender ni recolorear la carcasa para ocultar el problema.

1. Activar Gola y sus descendientes en GBC01 y GBC02 en Fusion.
2. Guardar los diseños y actualizar las inserciones vinculadas en la cocina.
3. Exportar con v0.1.5; comprobar perfiles visibles y BODY_EXCLUDED sin fallo
   de teselación para el auxiliar KitchenBar/Body1.
4. Regenerar imágenes y visor; revisar franjas negras con el operador.

## Trabajo posterior

- Ajustes de muebles en Fusion por el usuario y validación con segunda cocina.
- Catálogos/muestras reales de proveedores locales. Verde olivo, negro mate,
  blanco y pared perla/beige son una paleta ilustrativa aprobada visualmente,
  no SKUs calibrados ni aprobación de fabricación.
- Automatizar el flujo completo con un comando reutilizable; la orquestación
  usada para estas pruebas aún es local. Agente en español después del flujo
  determinista; no hay endpoint de trabajos ni publicación de resultados.
- Identidades actuales son de snapshot, no estables entre exportaciones.
- Mantener mm en Fusion/paquete y metros en Blender/GLB; Y-up de Fusion se
  convierte a Z-up en Blender y a Y-up en glTF una sola vez por frontera.
