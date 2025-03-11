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

        // Get the correct coordinates accounting for scroll position
        const rect = plotBackground.getBoundingClientRect();
        const scrollX = window.pageXOffset || document.documentElement.scrollLeft;
        const scrollY = window.pageYOffset || document.documentElement.scrollTop;

        console.log('Chart dimensions:', rect);
        console.log('Scroll position:', { scrollX, scrollY });

        // Use absolute positions (accounting for scroll)
        const startX = rect.x;
        const endX = rect.x + rect.width;
        const centerY = rect.y + (rect.height / 2);

        let x = endX;
        const y = centerY;
        let lastDate = null;
        const dataPoints = [];

        cursor.style.left = (x + scrollX) + 'px';
        cursor.style.top = (y + scrollY) + 'px';

        while (x > startX && dataPoints.length < target_points) {
            // Update cursor position with scroll offsets
            cursor.style.left = (x + scrollX) + 'px';
            cursor.style.top = (y + scrollY) + 'px';
            
            // Create and dispatch events (clientX/Y are viewport coordinates)
            const moveEvent = new MouseEvent('mousemove', {
                bubbles: true,
                clientX: x,
                clientY: y,
                view: window
            });
            plotBackground.dispatchEvent(moveEvent);
            
            // Get tooltip data by searching the entire document
            const dateElement = document.querySelector('.tooltip-date');
            const valueElement = document.querySelector('.tooltip-value');

            if (dateElement) {
                const date = dateElement.textContent;
                const value = valueElement?.textContent;  // Optional value
                
                // Only proceed if the date is present and unique
                if (date && date !== lastDate) {
                    dataPoints.push({
                        date: date.trim(),
                        value: value ? value.trim() : "NaN",
                        x: x,
                        y: y
                    });
                    lastDate = date;
                    
                    console.log(`Found data point: ${date.trim()} = ${value ? value.trim() : "NaN"}`);
                    
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