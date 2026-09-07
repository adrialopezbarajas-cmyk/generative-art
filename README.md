# ✨ Generador de Arte Generativo

Un proyecto interactivo que genera arte visual único y dinámico usando Canvas HTML5 y algoritmos pseudo-aleatorios.

## 🎨 Características

- **Arte dinámico**: Genera patrones visuales únicos cada vez que lo uses
- **Controles interactivos**: Ajusta en tiempo real:
  - 🎲 **Complejidad**: Controla cuántas formas se dibujan
  - 📏 **Escala**: Ajusta el tamaño de los elementos
  - 🔄 **Rotación**: Rota la composición completa
  - 🌊 **Densidad**: Aumenta o disminuye las capas
  - 🌈 **Velocidad de Color**: Modifica la variación de colores
  - 💡 **Brillo**: Ajusta la intensidad de las formas

- **Interacción**: Haz clic en el lienzo para generar arte aleatorio instantáneamente
- **Descarga**: Exporta tu arte como imagen PNG

## 🚀 Cómo usar

1. Abre `generative-art/index.html` en tu navegador
2. Ajusta los deslizadores para personalizar el arte
3. Haz clic en "Generar Nuevo" para cambiar la semilla aleatoria
4. Haz clic en "Descargar PNG" para guardar tu creación
5. Usa "Reiniciar" para volver a los valores por defecto

## 💻 Requisitos

- Navegador moderno compatible con HTML5 Canvas
- No requiere dependencias externas

## 🔧 Estructura

```
.
├── README.md              # Este archivo
└── generative-art/
    └── index.html         # Aplicación completa (HTML + CSS + JavaScript)
```

## 🎯 Cómo funciona

El generador utiliza:
- **Seeded Random**: Una función pseudo-aleatoria basada en semillas para reproducibilidad
- **Capas**: Múltiples capas de formas (círculos, rectángulos, triángulos, estrellas)
- **Colores HSL**: Sistema de colores dinámicos basado en la velocidad y configuración
- **Transformaciones Canvas**: Rotación y escalado para efectos visuales

## 📝 Personalización

Puedes modificar los valores predeterminados editando el archivo `generative-art/index.html`:

- **Colores base**: Edita la variable `#667eea` en los estilos CSS
- **Tipos de formas**: Modifica el switch en la función `draw()` para agregar nuevas formas
- **Rango de controles**: Ajusta los atributos `min`, `max` y `step` en los inputs

## 🎬 Ejemplos

Para crear diferentes estilos:
- **Abstracto limpio**: Complejidad baja, Densidad baja
- **Caótico colorido**: Complejidad alta, Velocidad de Color alta
- **Minimalista**: Brillo bajo, Densidad baja, Escala alta

## 📄 Licencia

Proyecto personal de experimentación creativa.

---

**Hecho con ❤️ por Adría**
