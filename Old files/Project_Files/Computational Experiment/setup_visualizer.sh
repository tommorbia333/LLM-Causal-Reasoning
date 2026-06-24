#!/bin/bash
# Run this from the root of your narrative-event-graphs repo.
# It creates a minimal Vite + React app for the visualizer.
#
# Prerequisites: Node.js installed (check with `node --version`)
# If you don't have it: brew install node

set -e

echo "Setting up visualizer..."

# Create the Vite project structure
mkdir -p visualizer/src

# Create package.json
cat > visualizer/package.json << 'EOF'
{
  "name": "event-graph-visualizer",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "d3": "^7.8.5"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.2.0",
    "vite": "^5.0.0"
  }
}
EOF

# Create vite config
cat > visualizer/vite.config.js << 'EOF'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
})
EOF

# Create index.html
cat > visualizer/index.html << 'EOF'
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Event Graph Visualizer</title>
    <style>
      * { margin: 0; padding: 0; box-sizing: border-box; }
    </style>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
EOF

# Create main.jsx entry point
cat > visualizer/src/main.jsx << 'EOF'
import React from 'react'
import ReactDOM from 'react-dom/client'
import EventGraphVisualizer from './EventGraphVisualizer.jsx'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <EventGraphVisualizer />
  </React.StrictMode>
)
EOF

echo "Installing dependencies..."
cd visualizer
npm install

echo ""
echo "Done! To run the visualizer:"
echo ""
echo "  cd visualizer"
echo "  npm run dev"
echo ""
echo "Then open http://localhost:5173 in your browser."
echo "Copy your EventGraphVisualizer.jsx into visualizer/src/ to update it."
