/**
 * Gets first and last data points from chart tooltips
 * @param {Object} options - Configuration options
 * @returns {Promise<Object>} Object containing start and end dates and values
 */
function getFirstLastDates(options = {}) {
    const defaultOptions = {
      waitTime: 100,  // ms to wait for tooltip to appear
      yPositionRatio: 0.5,  // Middle of chart
      leftOffset: 5,  // Small offset from edges to ensure we hit data points
      rightOffset: 5
    };
    
    const config = { ...defaultOptions, ...options };
    
    return new Promise((resolve, reject) => {
      try {
        // Find the chart and plot background elements
        const chartElement = document.querySelector('#chart');
        const plotBackground = document.querySelector('.highcharts-plot-background');
        
        if (!chartElement || !plotBackground) {
          return reject(new Error("Chart elements not found"));
        }
        
        // Get dimensions
        const plotRect = plotBackground.getBoundingClientRect();
        
        // Calculate positions
        const leftX = plotRect.left + config.leftOffset;
        const rightX = plotRect.right - config.rightOffset;
        const yPos = plotRect.top + (plotRect.height * config.yPositionRatio);
        
        // Result object
        const result = {
          start_date: null,
          start_value: null,
          end_date: null,
          end_value: null,
          unit_str: null
        };
        
        // Helper function to extract tooltip data
        function extractTooltipData() {
          const dateElement = document.querySelector('.tooltip-date');
          const valueElement = document.querySelector('.tooltip-value');
          
          let dateValue = null;
          let numericValue = null;
          let unitStr = '';
          
          if (dateElement) {
            const dateText = dateElement.textContent.trim();
            // Handle quarterly data formatting
            let processedDateText = dateText
              .replace('Q1', 'January')
              .replace('Q2', 'April')
              .replace('Q3', 'July')
              .replace('Q4', 'October');
            
            try {
              dateValue = new Date(processedDateText).toISOString();
            } catch (e) {
              console.log("Date parsing error:", e, "for text:", processedDateText);
            }
          }
          
          if (valueElement) {
            const valueText = valueElement.textContent.trim();
            // Parse numeric value with metric prefix handling
            let match = valueText.match(/(-?[\d,.\s]+)([KMBT])?/);
            if (match) {
              let value = match[1].replace(/,/g, '').trim();
              value = parseFloat(value);
              
              // Handle metric prefixes
              if (match[2]) {
                const multipliers = { 'K': 1000, 'M': 1000000, 'B': 1000000000, 'T': 1000000000000 };
                value *= multipliers[match[2]] || 1;
              }
              
              numericValue = value;
              
              // Extract unit string (everything after the numeric part)
              const remainingText = valueText.substring(valueText.indexOf(match[0]) + match[0].length).trim();
              unitStr = remainingText;
            }
          }
          
          return { dateValue, numericValue, unitStr };
        }
        
        // Function to simulate mouse movement
        function simulateMouseMove(x, y) {
          const event = new MouseEvent('mousemove', {
            view: window,
            bubbles: true,
            cancelable: true,
            clientX: x,
            clientY: y
          });
          plotBackground.dispatchEvent(event);
        }
        
        // Get left position data
        simulateMouseMove(leftX, yPos);
        
        setTimeout(() => {
          const leftData = extractTooltipData();
          result.start_date = leftData.dateValue;
          result.start_value = leftData.numericValue;
          
          if (leftData.unitStr) {
            result.unit_str = leftData.unitStr;
          }
          
          // Now get right position data
          simulateMouseMove(rightX, yPos);
          
          setTimeout(() => {
            const rightData = extractTooltipData();
            result.end_date = rightData.dateValue;
            result.end_value = rightData.numericValue;
            
            if (!result.unit_str && rightData.unitStr) {
              result.unit_str = rightData.unitStr;
            }
            
            resolve(result);
          }, config.waitTime);
        }, config.waitTime);
      } catch (error) {
        reject(new Error(`Script execution error: ${error.message}`));
      }
    });
  }
  
  // Entry point for Selenium execution
  const done = arguments[0]; // Callback provided by Selenium for async script
  const options = arguments[1] || {}; // Optional configuration
  
  getFirstLastDates(options)
    .then(result => {
      done(result);
    })
    .catch(error => {
      done({ error: error.toString() });
    });