function simulateManualMouseMovement() {
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
        
        // Function to check for tooltip elements
        function checkTooltipElements() {
            const tooltip = document.querySelector('.highcharts-tooltip');
            const tooltipDate = document.querySelector('.tooltip-date');
            const tooltipValue = document.querySelector('.tooltip-value');
            
            return {
                tooltipExists: !!tooltip,
                tooltipDateExists: !!tooltipDate,
                tooltipValueExists: !!tooltipValue,
                anyTooltip: !!tooltip || !!tooltipDate || !!tooltipValue
            };
        }
        
        // Initial state
        const initialState = checkTooltipElements();
        console.log("Initial tooltip state:", initialState);
        
        // Find the chart instance
        let chart = null;
        if (window.Highcharts && Highcharts.charts) {
            chart = Highcharts.charts.find(c => c);
        }
        
        // Function to create and dispatch mouse events
        function dispatchMouseEvent(target, type, x, y) {
            const event = new MouseEvent(type, {
                view: window,
                bubbles: true,
                cancelable: true,
                clientX: x,
                clientY: y,
                screenX: x,
                screenY: y,
                movementX: 1,  // Important for realistic movement
                movementY: 0,
                buttons: 0
            });
            
            target.dispatchEvent(event);
        }
        
        // Calculate points for realistic mouse movement path
        const startX = window.innerWidth / 2;  // Start from middle of screen
        const startY = window.innerHeight / 2;
        const endX = rect.left + rect.width / 2;  // End at center of chart
        const endY = rect.top + rect.height / 2;
        
        // Create a smooth path with multiple points
        const numSteps = 20;
        const path = [];
        
        for (let i = 0; i <= numSteps; i++) {
            const ratio = i / numSteps;
            path.push({
                x: startX + (endX - startX) * ratio,
                y: startY + (endY - startY) * ratio
            });
        }
        
        // Function to execute the realistic movement with proper timing
        return new Promise((resolve) => {
            // First event: mouseenter window
            dispatchMouseEvent(document.documentElement, 'mouseenter', startX, startY);
            
            // Then execute the path with slight delays between each point
            let step = 0;
            
            function nextStep() {
                if (step < path.length) {
                    const point = path[step];
                    
                    // Determine target element at this position
                    const elementAtPoint = document.elementFromPoint(point.x, point.y);
                    
                    // Fire appropriate events based on element changes
                    if (step > 0) {
                        const prevPoint = path[step - 1];
                        const prevElement = document.elementFromPoint(prevPoint.x, prevPoint.y);
                        
                        if (prevElement !== elementAtPoint) {
                            // We've moved to a new element
                            if (prevElement) {
                                dispatchMouseEvent(prevElement, 'mouseout', point.x, point.y);
                                dispatchMouseEvent(prevElement, 'mouseleave', point.x, point.y);
                            }
                            if (elementAtPoint) {
                                dispatchMouseEvent(elementAtPoint, 'mouseenter', point.x, point.y);
                                dispatchMouseEvent(elementAtPoint, 'mouseover', point.x, point.y);
                            }
                        }
                    }
                    
                    // Always fire mousemove
                    if (elementAtPoint) {
                        dispatchMouseEvent(elementAtPoint, 'mousemove', point.x, point.y);
                    }
                    
                    // If we're at the chart
                    if (elementAtPoint === plotArea || elementAtPoint === container) {
                        console.log(`Mouse over chart at step ${step}`);
                    }
                    
                    step++;
                    setTimeout(nextStep, 10);  // 10ms between movements (100 movements/second)
                } else {
                    // Movement complete
                    console.log("Manual mouse movement simulation completed");
                    
                    // Add a small delay for tooltip stabilization
                    setTimeout(() => {
                        const afterMoveState = checkTooltipElements();
                        console.log("After movement tooltip state:", afterMoveState);
                        
                        // Wait a bit more
                        setTimeout(() => {
                            // Now try to clear the tooltip
                            console.log("Now moving mouse away to clear tooltip");
                            
                            // Move far away from chart
                            dispatchMouseEvent(document.body, 'mousemove', 5, 5);
                            
                            // Check final state
                            setTimeout(() => {
                                const finalState = checkTooltipElements();
                                console.log("Final tooltip state:", finalState);
                                
                                resolve({
                                    success: true,
                                    initialState: initialState,
                                    afterMoveState: afterMoveState,
                                    finalState: finalState,
                                    hasChart: !!chart
                                });
                            }, 100);
                        }, 300);
                    }, 200);
                }
            }
            
            // Start the movement sequence
            nextStep();
        });
    } catch(e) {
        return {
            success: false,
            error: e.toString()
        };
    }
}

return simulateManualMouseMovement();