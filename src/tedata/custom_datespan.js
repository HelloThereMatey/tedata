function setDateSpan(start_date, end_date, done) {
    try {
        // Click calendar toggle button
        var toggleButton = document.querySelector('#dateInputsToggle');
        if (!toggleButton) {
            done({ success: false, error: "Calendar toggle button not found" });
            return;
        }
        toggleButton.click();
        
        // Small delay to ensure inputs are visible
        setTimeout(function() {
            // Find the date input fields
            var startInput = document.getElementById('d1');
            var endInput = document.getElementById('d2');
            
            if (!startInput || !endInput) {
                done({ success: false, error: "Date inputs not found" });
                return;
            }
            
            // Clear and set values
            startInput.value = '';
            endInput.value = '';
            startInput.value = start_date;
            endInput.value = end_date;
            
            // Trigger change events to ensure the chart updates
            var event = new Event('change', { bubbles: true });
            startInput.dispatchEvent(event);
            endInput.dispatchEvent(event);
            
            // Press enter on the end input to submit
            var keyEvent = new KeyboardEvent('keydown', {
                key: 'Enter',
                code: 'Enter',
                keyCode: 13,
                which: 13,
                bubbles: true
            });
            endInput.dispatchEvent(keyEvent);
            
            // Success - return additional diagnostic fields so the Python caller can verify what was set
            done({ 
                success: true,
                message: 'Date inputs set',
                start_date: start_date,
                end_date: end_date,
                startInputValue: startInput.value,
                endInputValue: endInput.value
            });
        }, 100);
    } catch (error) {
        done({ success: false, error: error.toString() });
    }
}

// Selenium will pass its callback and arguments
const start_date = arguments[0];
const end_date = arguments[1];
const seleniumCallback = arguments[2];

setDateSpan(start_date, end_date, seleniumCallback);