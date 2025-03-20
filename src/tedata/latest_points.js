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

function processDataPoint(x, y, dateElement, valueElement, dataPoints, lastDate, target_points, cursor) {
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
                return { complete: true, lastDate: date };
            }
        }
    }
    return { complete: false, lastDate };
}

async function moveCursor(options, done) {
    let cursor = null;
    const dataPoints = [];
    let lastDate = null;
    
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
        cursor = document.createElement('div');
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

        // Calculate all positions first
        const centerY = rect.y + (rect.height / 2);
        const startX = rect.x; // 
        const endX = rect.x + rect.width; // 

        // // First put cursor in middle, make tooltip appear, and click
        // const middleX = rect.x + (rect.width / 2);
        // cursor.style.left = (middleX + scrollX) + 'px';
        // cursor.style.top = (centerY + scrollY) + 'px';

        // // Create and dispatch mousemove event to position cursor
        // const initialMoveEvent = new MouseEvent('mousemove', {
        //     bubbles: true,
        //     clientX: middleX,
        //     clientY: centerY,
        //     view: window
        // });
        // plotBackground.dispatchEvent(initialMoveEvent);

        // // Add mouse click event at the center
        // console.log("Clicking at center of chart");
        // const clickEvent = new MouseEvent('click', {
        //     bubbles: true,
        //     cancelable: true,
        //     view: window,
        //     clientX: middleX,
        //     clientY: centerY
        // });
        // plotBackground.dispatchEvent(clickEvent);

        // // Wait at center position with cursor visible
        // await sleep(100);

        // Set starting position at right edge
        let x = endX;
        const y = centerY;

        // Move cursor and collect the rest of the data points
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

            // Process data point
            const result = processDataPoint(x, y, dateElement, valueElement, dataPoints, lastDate, target_points, cursor);
            if (result.complete) {
                done({
                    dataPoints: dataPoints,
                    logs: logs
                });
                return;
            }
            lastDate = result.lastDate;
            
            await sleep(wait_time_override || 25);
            x -= increment;
        }
        
        // Explicitly check left edge
        x = startX;
        cursor.style.left = (x + scrollX) + 'px';
        cursor.style.top = (y + scrollY) + 'px';
        
        const leftEdgeEvent = new MouseEvent('mousemove', {
            bubbles: true,
            clientX: x,
            clientY: y,
            view: window
        });
        plotBackground.dispatchEvent(leftEdgeEvent);
        
        // Wait for tooltip to appear
        await sleep(150);
        
        // Check for left edge tooltip
        const leftDateElement = document.querySelector('.tooltip-date');
        const leftValueElement = document.querySelector('.tooltip-value');
        processDataPoint(x, y, leftDateElement, leftValueElement, dataPoints, lastDate, target_points, cursor);
        
        // Reached left edge
        cursor.remove();
        console.log(`Collected ${dataPoints.length} points, reached end of chart`);
        done({
            dataPoints: dataPoints,
            logs: logs
        });
        
    } catch (error) {
        console.error('Error:', error);
        if (cursor) cursor.remove();
        done({
            dataPoints: dataPoints || [],
            error: error.toString(),
            logs: logs
        });
    }
}

// Modified argument handling
const done = arguments[arguments.length - 1];
const options = arguments[0] || {};
moveCursor(options, done);