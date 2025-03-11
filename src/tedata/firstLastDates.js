/**
 * Gets first and last data points from chart tooltips
 * using a direct and simple approach
 */
function getFirstLastDates(done) {
    const logs = [];
    function log(message) {
        logs.push(message);
        console.log(message);
    }
    
    try {
        // Find chart dimensions
        const plotBackground = document.querySelector('.highcharts-plot-background');
        if (!plotBackground) {
            log('Plot background not found');
            return done({ error: 'Plot background not found', logs });
        }
        
        const plotRect = plotBackground.getBoundingClientRect();
        log(`Plot area: left=${plotRect.left}, right=${plotRect.right}, width=${plotRect.width}, height=${plotRect.height}`);
        
        const result = {
            start_date: null,
            start_value: null,
            end_date: null,
            end_value: null,
            unit_str: null,
            debug: { logs }
        };
        
        // Function to extract tooltip data with retry
        function getTooltipData(retries = 5, delay = 100) {
            return new Promise(resolve => {
                let attempts = 0;
                
                function check() {
                    const dateEl = document.querySelector('.tooltip-date');
                    const valueEl = document.querySelector('.tooltip-value');
                    
                    if (dateEl && valueEl) {
                        resolve({
                            date: dateEl.textContent.trim(),
                            value: valueEl.textContent.trim()
                        });
                    } else if (++attempts < retries) {
                        setTimeout(check, delay);
                    } else {
                        resolve(null);
                    }
                }
                
                check();
            });
        }
        
        // Function to process and store tooltip data
        function processTooltip(tooltipData, position) {
            if (!tooltipData) return;
            
            log(`Found tooltip at ${position}: ${JSON.stringify(tooltipData)}`);
            
            // Parse numeric value
            const valueText = tooltipData.value;
            const match = valueText.match(/(-?[\d,.\s]+)([KMBT])?/);
            
            if (match) {
                let value = match[1].replace(/,/g, '').replace(/\s/g, '').trim();
                value = parseFloat(value);
                
                if (match[2]) {
                    const multipliers = { 
                        'K': 1000, 
                        'M': 1000000, 
                        'B': 1000000000, 
                        'T': 1000000000000 
                    };
                    value *= multipliers[match[2]] || 1;
                }
                
                if (position === 'left') {
                    result.start_date = tooltipData.date;
                    result.start_value = value;
                } else {
                    result.end_date = tooltipData.date;
                    result.end_value = value;
                }
                
                // Extract unit string
                const remainingText = valueText.substring(valueText.indexOf(match[0]) + match[0].length).trim();
                result.unit_str = remainingText || result.unit_str;
            }
        }
        
        async function executeSearch() {
            // Calculate precise positions
            const centerY = plotRect.top + (plotRect.height / 2);
            const leftX = plotRect.left; // Start at left and right exxtremes of plot background.
            const rightX = plotRect.right; // 
            
            // Get first point (left edge)
            log(`Checking left point at x=${leftX}, y=${centerY}`);
            
            // Create a MouseEvent that uses pageX/Y instead of clientX/Y to handle scrolling
            const leftEvent = new MouseEvent('mousemove', {
                bubbles: true,
                cancelable: true,
                view: window,
                clientX: leftX,
                clientY: centerY
            });
            
            // Dispatch event on plot background element
            plotBackground.dispatchEvent(leftEvent);
            
            // Wait and get tooltip data
            const leftData = await getTooltipData();
            processTooltip(leftData, 'left');
            
            // Clear by moving away
            const clearEvent = new MouseEvent('mouseout', {
                bubbles: true,
                cancelable: true,
                view: window
            });
            plotBackground.dispatchEvent(clearEvent);
            
            // Wait before continuing
            await new Promise(r => setTimeout(r, 300));
            
            // Get last point (right edge)
            log(`Checking right point at x=${rightX}, y=${centerY}`);
            
            const rightEvent = new MouseEvent('mousemove', {
                bubbles: true,
                cancelable: true,
                view: window,
                clientX: rightX,
                clientY: centerY
            });
            
            plotBackground.dispatchEvent(rightEvent);
            
            // Wait and get tooltip data
            const rightData = await getTooltipData();
            processTooltip(rightData, 'right');
            
            // Done
            log('Extraction complete');
            done(result);
        }
        
        executeSearch();
        
    } catch (error) {
        log(`Error: ${error.message}`);
        done({ error: error.toString(), logs });
    }
}

// Selenium will pass its callback as the first argument
const seleniumCallback = arguments[0];
getFirstLastDates(seleniumCallback);