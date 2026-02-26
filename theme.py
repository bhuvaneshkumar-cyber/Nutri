from nicegui import ui

def apply_theme():
    ui.add_head_html('''
    <style>
        body { 
            background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%); 
            color: #1b5e20; 
            font-family: 'Segoe UI', system-ui, sans-serif;
            min-height: 100vh;
            margin: 0;
        }
        /* Glassmorphism card effect */
        .glass-card { 
            background: rgba(255, 255, 255, 0.65); 
            backdrop-filter: blur(12px); 
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.8); 
            border-radius: 16px; 
            box-shadow: 0 8px 32px 0 rgba(76, 175, 80, 0.15);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        .glass-card:hover {
            box-shadow: 0 12px 40px 0 rgba(76, 175, 80, 0.25);
        }
        /* Glistening text effect for headers */
        .glisten-text { 
            background: linear-gradient(to right, #2e7d32, #4caf50, #2e7d32);
            background-size: 200% auto;
            color: #000;
            background-clip: text;
            text-fill-color: transparent;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            animation: shine 3s linear infinite;
        }
        @keyframes shine {
            to { background-position: 200% center; }
        }
        .accessible-text {
            color: #1a4314; /* High contrast dark green */
        }
    </style>
    ''')