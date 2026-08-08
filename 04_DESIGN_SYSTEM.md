# Design System

## Principios de Diseño

- **Minimalist**: Cero decoración, máxima señal
- **Dark-first**: Fondo oscuro (profesional, cansa menos), texto claro
- **Accesible**: WCAG 2.1 AA, colores con contraste 4.5:1+
- **Responsive**: Mobile first, viewport configurado
- **Semantic HTML**: Sin divitis innecesaria

## Tipografía

```css
/* Stack de fuentes */
font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;

/* Tamaños */
h1: 2rem (32px)
h2: 1.5rem (24px)
h3: 1.25rem (20px)
body: 1rem (16px)
small: 0.875rem (14px)
code: 0.8rem (13px)
```

## Paleta de Colores

### Dark Theme (por defecto)

```
Background: #0f1115
Surface:   #161923
Border:    #262b3a
Text:      #e6e8eb
Text Muted: #9aa4b2 / #6b7280

Semantic:
├── Success: #6fd48a (verde claro)
│   ├── Dark BG: #14361f
│   └── Light BG: #e8f5e9
│
├── Error: #f28b8b (rojo claro)
│   ├── Dark BG: #3a1414
│   └── Light BG: #ffebee
│
├── Warning: #e6c46b (amarillo)
│   ├── Dark BG: #3a2f10
│   └── Light BG: #fff8e1
│
├── Info: #6ea8fe (azul)
│   ├── Dark BG: #1e3a8a
│   └── Light BG: #e3f2fd
│
└── Neutral: #262b3a
    └── Dark BG: #262b3a
```

### Light Theme (future)
Invertir:
- Text: #0f1115
- Background: #ffffff
- Surface: #f5f5f5
- Border: #e0e0e0

## Componentes

### Forms

**Input Text / Password**
```html
<input type="text" 
  style="
    width: 100%;
    padding: 0.5rem;
    margin: 0.5rem 0 1rem;
    background: #0f1115;
    border: 1px solid #262b3a;
    border-radius: 4px;
    color: #e6e8eb;
  " />
```

**Button (Primary)**
```css
background: #2f6fed;
color: white;
border: none;
padding: 0.5rem 1rem;
border-radius: 4px;
cursor: pointer;
font-size: 0.9rem;

/* Hover */
background: #1e5bc8;

/* Disabled */
background: #6b7280;
cursor: not-allowed;
```

**Button (Secondary)**
```css
background: #262b3a;
color: #9aa4b2;
border: none;
```

**Label**
```css
display: block;
margin-top: 1rem;
margin-bottom: 0.25rem;
font-weight: 500;
font-size: 0.9rem;
color: #e6e8eb;
```

### Messages

**Error**
```css
color: #f28b8b;
background: #3a1414;
padding: 0.75rem 1rem;
border-radius: 4px;
margin-bottom: 1rem;
font-size: 0.9rem;
```

**Success**
```css
color: #6fd48a;
background: #14361f;
padding: 0.75rem 1rem;
border-radius: 4px;
margin-bottom: 1rem;
font-size: 0.9rem;
```

### Cards

```css
background: #161923;
border: 1px solid #262b3a;
border-radius: 8px;
padding: 1rem 1.25rem;
margin-bottom: 1.25rem;
```

### Tables

```css
width: 100%;
border-collapse: collapse;
font-size: 0.9rem;

th {
  text-align: left;
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid #1f2330;
  color: #9aa4b2;
  font-weight: 500;
}

td {
  text-align: left;
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid #1f2330;
}

tr:hover {
  background: #0a0b0e;
}
```

### Badges

```css
display: inline-block;
padding: 0.1rem 0.5rem;
border-radius: 999px;
font-size: 0.75rem;
font-weight: 600;

.badge-ok {
  background: #14361f;
  color: #6fd48a;
}

.badge-fail {
  background: #3a1414;
  color: #f28b8b;
}

.badge-unknown {
  background: #262b3a;
  color: #9aa4b2;
}

.badge-devps {
  background: #14361f;
  color: #6fd48a;
}

.badge-adopted {
  background: #3a2f10;
  color: #e6c46b;
}
```

### Code / Pre

```css
background: #0a0b0e;
padding: 1rem;
border-radius: 6px;
overflow-x: auto;
font-size: 0.8rem;
font-family: "Monaco", "Menlo", "Courier New", monospace;
max-height: 500px;
overflow-y: auto;
```

## Spacing (8px grid)

```
xs: 0.25rem (4px)
sm: 0.5rem (8px)
md: 1rem (16px)
lg: 1.25rem (20px)
xl: 1.5rem (24px)
2xl: 2rem (32px)
```

## Border Radius

```
sm: 4px (inputs, buttons)
md: 6px (cards, pre)
lg: 8px (modals, larger components)
full: 999px (badges, pills)
```

## Shadows (subtle)

```css
box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
```

## Responsive Breakpoints

```
mobile: < 640px (no breakpoint, mobile-first)
tablet: 640px+
desktop: 1024px+
```

### Mobile Considerations

- Viewport meta tag: `<meta name="viewport" content="width=device-width, initial-scale=1">`
- Touch targets: mínimo 44x44px
- Buttons: full width en mobile, 120px+ en desktop
- Horizontal scroll: NEVER
- Max-width en main: 1100px

## Accessibility

- Color contrast: 4.5:1 para texto normal, 3:1 para large text
- Focus states: outline visible en inputs/buttons
- Labels asociados a inputs: `<label for="id">`
- Semantic HTML: `<button>`, `<form>`, `<header>`, `<nav>`, `<main>`
- Alt text: N/A (dashboard no usa imágenes)
- Keyboard nav: todos los elementos interactivos

## Example: Login Form

```html
<form class="login" method="post" action="/dashboard/login">
  <h2>devps</h2>
  
  {% if error %}
    <div style="color: #f28b8b; margin-bottom: 1rem;">
      {{ error }}
    </div>
  {% endif %}
  
  <label for="username">Username</label>
  <input type="text" id="username" name="username" required autofocus 
    style="width: 100%; padding: 0.5rem; margin: 0.5rem 0 1rem; 
           background: #0f1115; border: 1px solid #262b3a; 
           border-radius: 4px; color: #e6e8eb;">
  
  <label for="password">Password</label>
  <input type="password" id="password" name="password" required 
    style="width: 100%; padding: 0.5rem; margin: 0.5rem 0 1rem; 
           background: #0f1115; border: 1px solid #262b3a; 
           border-radius: 4px; color: #e6e8eb;">
  
  <button type="submit" 
    style="width: 100%; padding: 0.75rem; background: #2f6fed; 
           color: white; border: none; border-radius: 4px; 
           cursor: pointer; font-size: 1rem; font-weight: 500;">
    Log in
  </button>
</form>
```

## Roadmap (Future)

- [ ] Dark/Light mode toggle
- [ ] Custom CSS variables
- [ ] Animation library (framer-motion equivalent)
- [ ] Icon set (SVG)
- [ ] Storybook para componentes
