/**
 * Gets first and last data points from chart tooltips
 * by accurately targeting the plot border
 */
function getFirstLastDates(done) {
    // Create a logging mechanism
    const logs = [];
    function log(message) {
        logs.push(message);
        console.log(message);
    }

    log('Starting first/last date extraction using plot border targeting');
    
    try {
        // Find the plot border element directly
        const plotBorder = document.querySelector('.highcharts-plot-border');
        if (!plotBorder) {
            log('Plot border not found, falling back to plot background');
            const plotBackground = document.querySelector('.highcharts-plot-background');
            if (!plotBackground) {
                log('Plot background not found either');
                return done({ error: 'Chart elements not found', logs });
            }
            
            const rect = plotBackground.getBoundingClientRect();
            log(`Using plot background dimensions: x=${rect.x}, y=${rect.y}, width=${rect.width}, height=${rect.height}`);
        }
        
        // Get the exact coordinates from the plot border attributes
        const x = parseFloat(plotBorder.getAttribute('x'));
        const y = parseFloat(plotBorder.getAttribute('y'));
        const width = parseFloat(plotBorder.getAttribute('width'));
        const height = parseFloat(plotBorder.getAttribute('height'));
        
        // Get bounding client rect for absolute positioning
        const plotBorderRect = plotBorder.getBoundingClientRect();
        const leftX = plotBorderRect.left ; // Slight offset to ensure we hit data
        const rightX = plotBorderRect.right ; // Slight offset to ensure we hit data
        const centerY = plotBorderRect.top + plotBorderRect.height / 2;
        
        log(`Plot border attributes: x=${x}, y=${y}, width=${width}, height=${height}`);
        log(`Calculated positions: leftX=${leftX}, rightX=${rightX}, centerY=${centerY}`);
        
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
        
        const result = {
            start_date: null,
            start_value: null,
            end_date: null,
            end_value: null,
            unit_str: null,
            debug: { logs }
        };
        
        // Function to move cursor and extract tooltip data
        function moveAndExtract(x, y, position) {
            return new Promise(resolve => {
                // Position cursor
                cursor.style.left = x + 'px';
                cursor.style.top = y + 'px';
                
                // Find plot background for event dispatching
                const plotBackground = document.querySelector('.highcharts-plot-background');
                
                // Create and dispatch events - explicitly using clientX/Y
                const moveEvent = new MouseEvent('mousemove', {
                    bubbles: true,
                    clientX: x,
                    clientY: y,
                    view: window
                });
                plotBackground.dispatchEvent(moveEvent);
                
                log(`Moved cursor to ${position} position: x=${x}, y=${y}`);
                
                // Wait for tooltip to appear
                setTimeout(() => {
                    // Get tooltip data by searching the entire document
                    const dateElement = document.querySelector('.tooltip-date');
                    const valueElement = document.querySelector('.tooltip-value');
                    
                    if (dateElement) {
                        const dateText = dateElement.textContent.trim();
                        log(`Found date element at ${position}: ${dateText}`);
                        
                        if (position === 'left') {
                            result.start_date = dateText;
                        } else {
                            result.end_date = dateText;
                        }
                        
                        if (valueElement) {
                            let valueText = valueElement.textContent.trim();
                            log(`Found value element at ${position}: ${valueText}`);
                            
                            // Parse numeric value with metric prefix handling
                            const match = valueText.match(/(-?[\d,.\s]+)([KMBT])?/);
                            if (match) {
                                let value = match[1].replace(/,/g, '').replace(/\s/g, '').trim();
                                value = parseFloat(value);
                                
                                // Handle metric prefixes
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
                                    result.start_value = value;
                                } else {
                                    result.end_value = value;
                                }
                                
                                // Extract unit string (everything after the numeric part)
                                const remainingText = valueText.substring(valueText.indexOf(match[0]) + match[0].length).trim();
                                result.unit_str = remainingText || result.unit_str;
                            } else {
                                log(`Unable to parse value from ${valueText}`);
                            }
                            
                            resolve(true);
                            return;
                        } else {
                            log(`No value element found at ${position} position`);
                        }
                    } else {
                        log(`No date element found at ${position} position`);
                    }
                    
                    resolve(false);
                }, 300);
            });
        }
        
        // Execute the extraction sequentially
        async function executeExtraction() {
          // Try left position with progressive offsets
          let success = false;
          let leftOffset = 0;  // Changed from 'Offset' to 'leftOffset'
          const maxOffset = 15;  // Maximum pixels to try
          
          log('Starting progressive search for left tooltip position');
          while (!success && leftOffset <= maxOffset) {
              log(`Trying left position with offset: ${leftOffset}px`);
              success = await moveAndExtract(leftX + leftOffset, centerY, 'left');
              if (!success) {
                  leftOffset += 1;
              }
          }
          
          // Reset success flag for right position
          success = false;
          let rightOffset = 0;
          
          log('Starting progressive search for right tooltip position');
          while (!success && rightOffset <= maxOffset) {
              log(`Trying right position with offset: ${rightOffset}px`);
              success = await moveAndExtract(rightX - rightOffset, centerY, 'right');
              if (!success) {
                  rightOffset += 1;
              }
          }
          
          cursor.remove();
          log('Extraction complete');
          done(result);
        }
        
        executeExtraction();
        
    } catch (error) {
        log(`Error: ${error.message}`);
        done({ error: error.toString(), logs });
    }
}

// Selenium will pass its callback as the first argument
const seleniumCallback = arguments[0];
getFirstLastDates(seleniumCallback);