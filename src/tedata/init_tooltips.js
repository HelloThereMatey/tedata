        function initializeTooltipSimple() {
            try {
                // Find chart container
                const container = document.querySelector('.highcharts-container');
                const plotArea = document.querySelector('.highcharts-plot-background');
                
                if (!container || !plotArea) {
                    return {
                        success: false,
                        error: "Could not find chart elements"
                    };
                }
                
                // Get dimensions
                const rect = plotArea.getBoundingClientRect();
                
                // Calculate center position
                const centerX = Math.floor(rect.left + rect.width / 2);
                const centerY = Math.floor(rect.top + rect.height / 2);
                
                // Function to check for tooltip elements
                function checkTooltipElements() {
                    const tooltip = document.querySelector('.highcharts-tooltip');
                    const tooltipDate = document.querySelector('.tooltip-date');
                    const tooltipValue = document.querySelector('.tooltip-value');
                    
                    return {
                        tooltipExists: !!tooltip,
                        tooltipDateExists: !!tooltipDate,
                        tooltipValueExists: !!tooltipValue
                    };
                }
                
                // Initial state
                const initialState = checkTooltipElements();
                
                // Create and dispatch a single mouse move event
                const event = new MouseEvent('mousemove', {
                    view: window,
                    bubbles: true,
                    cancelable: true,
                    clientX: centerX,
                    clientY: centerY,
                    buttons: 0
                });
                
                // Send to both container and plot area
                container.dispatchEvent(event);
                plotArea.dispatchEvent(event);
                
                // Find the chart instance to use the API directly if needed
                let chart = null;
                if (window.Highcharts && Highcharts.charts) {
                    chart = Highcharts.charts.find(c => c);
                    
                    // If we have a chart, also use its API to try to show the tooltip
                    if (chart && chart.tooltip) {
                        const series = chart.series[0];
                        if (series && series.points.length > 0) {
                            // Try to find a point in the middle
                            const middleIndex = Math.floor(series.points.length / 2);
                            const middlePoint = series.points[middleIndex];
                            
                            if (middlePoint) {
                                // Refresh the tooltip with this point
                                chart.tooltip.refresh(middlePoint);
                            }
                        }
                    }
                }
                
                // Final state
                const finalState = checkTooltipElements();
                
                return {
                    success: finalState.tooltipExists || 
                            finalState.tooltipDateExists || 
                            finalState.tooltipValueExists,
                    initialState: initialState,
                    finalState: finalState,
                    hasChart: !!chart
                };
                
            } catch(e) {
                return {
                    success: false,
                    error: e.toString()
                };
            }
        }
        
        return initializeTooltipSimple();