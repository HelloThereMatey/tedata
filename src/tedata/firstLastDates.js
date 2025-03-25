/**
 * Gets first and last data points from chart tooltips
 * and returns the raw tooltip data for Python parsing
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
            debug: { logs }
        };
        
        // Function to extract tooltip data with retry - handles partial tooltips
        function getTooltipData(retries = 5, delay = 100) {
          return new Promise(resolve => {
              let attempts = 0;
              
              function check() {
                  const dateEl = document.querySelector('.tooltip-date');
                  const valueEl = document.querySelector('.tooltip-value');
                  
                  // If we have either date or value element, consider it a success
                  if (dateEl || valueEl) {
                      resolve({
                          date: dateEl ? dateEl.textContent.trim() : null,
                          value: valueEl ? valueEl.textContent.trim() : null
                      });
                  } else if (++attempts < retries) {
                      setTimeout(check, delay);
                  } else {
                      // If we've tried enough times and found nothing, return null values
                      resolve({
                          date: null,
                          value: null
                      });
                  }
              }
              
              check();
          });
        }
        
        // Function to store tooltip data without parsing
        function storeTooltip(tooltipData, position) {
            if (!tooltipData) return;
            
            log(`Found tooltip at ${position}: ${JSON.stringify(tooltipData)}`);
            
            // Just store the raw data without parsing
            if (position === 'left') {
                result.start_date = tooltipData.date;
                result.start_value = tooltipData.value;
            } else {
                result.end_date = tooltipData.date;
                result.end_value = tooltipData.value;
            }
        }
        
        async function executeSearch() {
            //First clear any existing tooltips via mouseout event
            const outEvent = new MouseEvent('mouseout', {
                bubbles: true,
                cancelable: true,
                view: window
            });
            document.body.dispatchEvent(outEvent);
            
            //Calculate precise positions
            const centerY = plotRect.top + (plotRect.height / 2);
            const leftX = plotRect.left; // No offset
            const rightX = plotRect.right; // No offset
            
            // Get first point (left edge)
            log(`Checking left point at x=${leftX}, y=${centerY}`);
            
            const leftEvent = new MouseEvent('mousemove', {
                bubbles: true,
                cancelable: true,
                view: window,
                clientX: leftX,
                clientY: centerY
            });
            
            plotBackground.dispatchEvent(leftEvent);
            
            // Wait and get tooltip data
            const leftData = await getTooltipData();
            storeTooltip(leftData, 'left');
            
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
            storeTooltip(rightData, 'right');
            
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