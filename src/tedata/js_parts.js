// Set up logging
let logs = [];
const originalConsoleLog = console.log;
console.log = function() {
    logs.push(Array.from(arguments).join(' '));
    originalConsoleLog.apply(console, arguments);
};

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function getIncrement(points) {
    if (points === "all" || points > 48) return 1;
    if (points > 24) return 2;
    if (points > 12) return 4;
    return 5;
}

async function moveCursor(options, done) {
    try {
        // Destructure options with defaults
        const {
            num_points = 10,
            increment_override = null,
            wait_time_override = null
        } = options;

        console.log('Starting cursor movement, target points:', num_points);
        
        // Handle "all" option and set increment
        const increment = increment_override || getIncrement(num_points);
        let target_points = num_points === "all" ? Infinity : num_points;
        
        console.log(`Using increment: ${increment}px`);
        console.log(`Using wait time: ${wait_time_override || 25}ms`);
        
        // Create visible cursor for debugging
        const cursor = document.createElement('div');
        cursor.style.cssText = `
            position: absolute;
            width: 5px;
            height: 5px;
            background-color: red;
            border-radius: 50%;
            pointer-events: none;
            z-index: 999999;
        `;
        document.body.appendChild(cursor);

        // Get chart area
        const plotBackground = document.querySelector('.highcharts-plot-background');
        if (!plotBackground) {
            throw new Error('Plot background not found');
        }

        const rect = plotBackground.getBoundingClientRect();
        console.log('Chart dimensions:', rect);

        let x = rect.x + rect.width;
        const y = rect.y + rect.height / 2;
        let lastDate = null;
        const dataPoints = [];
        
        cursor.style.left = x + 'px';
        cursor.style.top = y + 'px';
        
        while (x > rect.x && dataPoints.length < target_points) {
            cursor.style.left = x + 'px';
            
            // Create and dispatch events
            const moveEvent = new MouseEvent('mousemove', {
                bubbles: true,
                clientX: x,
                clientY: y,
                view: window
            });
            plotBackground.dispatchEvent(moveEvent);
            
            // Get tooltip data - using more specific selector
            const tooltips = document.querySelectorAll('.highcharts-tooltip');
            const tooltip = Array.from(tooltips).find(t => 
                t.querySelector('.tooltip-date') && t.querySelector('.tooltip-value')
            );
            
            if (tooltip) {
                const dateElement = tooltip.querySelector('.tooltip-date');
                const valueElement = tooltip.querySelector('.tooltip-value');
                
                const date = dateElement?.textContent;
                const value = valueElement?.textContent;
                
                if (date && value && date !== lastDate) {
                    dataPoints.push({
                        date: date.trim(),
                        value: value.trim(),
                        x: x,
                        y: y
                    });
                    lastDate = date;
                    
                    if (dataPoints.length >= target_points && target_points !== Infinity) {
                        console.log(`Collected ${target_points} points, finishing...`);
                        cursor.remove();
                        done({
                            dataPoints: dataPoints,
                            logs: logs
                        });
                        return;
                    }
                }
            }
            
            await sleep(wait_time_override || 25);
            x -= increment;
        }
        
        // Reached left edge
        cursor.remove();
        console.log(`Collected ${dataPoints.length} points, reached end of chart`);
        done({
            dataPoints: dataPoints,
            logs: logs
        });
        
    } catch (error) {
        console.error('Error:', error);
        cursor?.remove();
        done({
            dataPoints: [],
            logs: logs
        });
    }
}

// Modified argument handling
const done = arguments[arguments.length - 1];
const options = arguments[0] || {};
moveCursor(options, done);