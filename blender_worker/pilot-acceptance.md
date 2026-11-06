# E17 — Piloto validado el 2026-11-05

Estado: implementación y revisión visual del primer piloto aceptadas por el
operador. El PR #6 puede pasar a revisión; el EPIC E17 completo sigue abierto.

## Exportación y etiquetas

- KaliTagRoles v0.4.5: 168 componentes ya correctos, cero escrituras y errores;
  solo KitchenBar quedó pendiente como contenedor. Guardar deshabilitado era
  coherente con una ejecución que no modificó el documento.
- KaliExportRender v0.1.6: 159 mallas, 259 instancias, cero fallos y 397 avisos.
  No quedaron definiciones con geometría sin rol. KitchenBar/Body1 se excluyó
  por confirmación explícita y quedó registrado como BODY_EXCLUDED.
- Los 16 cuerpos GOLA_PROFILE, incluidos los diez Profile_*, llegaron visibles
  y con negro mate. Los fillers siguen puertas/carcasa mediante finish_target;
  los faldones siguen encimera. Back_side es CARCASS_PANEL y Panel_door_lower DOOR.
- El diagnóstico leyó 227 definiciones, 168 con rol y cero lecturas recuperadas:
  los atributos fueron accesibles directamente en esta ejecución. La consulta
  alternativa por ID único se probó con mocks; no atribuirle causalmente este
  resultado ni afirmar que ya se ejerció con datos reales.
- El exportador sigue siendo de diagnóstico: 196 avisos de acabado y 196 de
  veta, más avisos de identidad/orientación/resolución y la exclusión confirmada.
  La paleta visual no equivale a SKUs comerciales ni aprobación de fabricación.

## Blender y esquina corregida

- Se importaron 196 cuerpos y pasaron 196 comprobaciones dimensionales
  independientes contra Fusion. El hash de geometría y transformaciones se
  conservó al renderizar; la visibilidad temporal de puertas se restauró.
- El bloque blanco que tapaba la esquina era el cubo inicial de Blender,
  identificado mediante ray casting. El GLB ya lo excluía, pero los PNG no.
  La explicación anterior de que se debía a la cámara era incorrecta.
- El renderer ahora crea una escena independiente con la colección fuente,
  accesorios y setup propios. Conserva la escena original con Cube, Camera y
  Light, pero esos objetos no participan en la presentación guardada.
- La comprobación de pertenencia pasó con 226 objetos permitidos. La
  reimportación GLB verificó 191 cuerpos visibles y conservó materiales y
  coordenadas, con error máximo medido de 0 mm.
- Se regeneraron perspectiva, frontal, interior y vista elevada. El operador
  confirmó que la esquina corregida se ve bien. Los archivos permanecen locales;
  no se publican modelos, imágenes, parámetros ni reportes del cliente.

## Verificación y límites

17 pruebas del exportador y una de TagRoles pasan. El worker mantiene 31
pruebas de paquete, configuración y colocación, más comprobaciones ejecutadas
en Blender para aislamiento de escena, geometría y conversión GLB.

La eliminación de escrituras de Description fue validada por el operador como
rápida. Los roles almacenados son la fuente de verdad; Description puede quedar
desactualizada. Las medidas siguen mm en Fusion/paquete y metros en Blender/GLB.

Pendientes posteriores: segunda cocina, correspondencia estable entre revisiones,
catálogo y muestras reales, automatización reutilizable del trabajo completo,
agente en español e integración persistente en Studio. El visor de Studio es
un piloto autenticado de archivos locales; no está desplegado ni asociado a
trabajos/revisiones de proyecto. El PR #6 tiene base feat/manufacturing-role-tags-bom;
su integración con main debe respetar esa dependencia.
