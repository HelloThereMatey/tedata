const logs = [];
console.log = function(msg) { logs.push(msg); };

// Declare cryptoDetection outside try block
let cryptoDetection = {
    cryptoJS: false,
    webCryptoAPI: false,
    forge: false,
    sjcl: false,
    suspiciousGlobals: [],
    error: null
};

try {
    // Check if Highcharts exists
    if (typeof Highcharts === 'undefined') {
        return { success: false, message: 'Highcharts not found', logs: logs, cryptoDetection: cryptoDetection };
    }
    
    // Find charts in the page
    if (!Highcharts.charts || Highcharts.charts.length === 0) {
        return { success: false, message: 'No Highcharts instances found', logs: logs, cryptoDetection: cryptoDetection };
    }
    
    // Find a valid chart
    const chart = Highcharts.charts.find(c => c && c.series && c.series.length > 0);
    if (!chart) {
        return { success: false, message: 'No valid chart with series found', logs: logs, cryptoDetection: cryptoDetection };
    }
    
    // Get basic chart info
    const info = {
        seriesCount: chart.series.length,
        pointsCount: chart.series[0]?.points?.length || 0,
        xAxisType: chart.xAxis[0]?.options?.type,
        chartType: chart.options?.chart?.type,
        hasTooltip: !!chart.tooltip
    };
    
    // CRYPTO DETECTION SECTION
    cryptoDetection = {
        cryptoJS: typeof CryptoJS !== 'undefined',
        webCryptoAPI: typeof crypto !== 'undefined' && typeof crypto.subtle !== 'undefined',
        forge: typeof forge !== 'undefined',
        sjcl: typeof sjcl !== 'undefined',
        suspiciousGlobals: []
    };

    // Check for crypto-related globals
    try {
        Object.getOwnPropertyNames(window).forEach(name => {
            const lowerName = name.toLowerCase();
            if (lowerName.includes('crypto') || 
                lowerName.includes('decrypt') || 
                lowerName.includes('cipher') ||
                lowerName.includes('aes') ||
                lowerName.includes('encrypt')) {
                cryptoDetection.suspiciousGlobals.push({
                    name: name, 
                    type: typeof window[name],
                    isFunction: typeof window[name] === 'function'
                });
            }
        });
    } catch (e) {
        cryptoDetection.error = e.message;
    }

    // Extract complete series data
    const seriesData = [];
    if (chart.series && chart.series.length > 0) {
        chart.series.forEach((series, idx) => {
            if (series && series.points && series.points.length > 0) {
                const points = series.points.map(point => ({
                    x: point.x,
                    y: point.y,
                    name: point.name || null,
                    category: point.category || null
                }));
                
                seriesData.push({
                    index: idx,
                    name: series.name || `Series ${idx}`,
                    type: series.type || chart.options?.chart?.type,
                    visible: series.visible !== false,
                    pointCount: series.points.length,
                    points: points
                });
            }
        });
    }
    
    // Try to get first and last points
    if (chart.series[0] && chart.series[0].points && chart.series[0].points.length) {
        const points = chart.series[0].points;
        const firstPoint = points[0];
        const lastPoint = points[points.length - 1];
        
        info.firstPointX = firstPoint.x;
        info.firstPointY = firstPoint.y;
        info.lastPointX = lastPoint.x;
        info.lastPointY = lastPoint.y;
        
        // Convert timestamps to readable dates
        info.firstDate = new Date(firstPoint.x).toISOString();
        info.lastDate = new Date(lastPoint.x).toISOString();
    }
    
    // Build the full result object
    const result = {
        success: true,
        message: 'Highcharts API accessed successfully',
        info: info,
        seriesData: seriesData,
        cryptoDetection: cryptoDetection,
        logs: logs
    };

    // Try to stringify for logging purposes (may fail on circular refs)
    try {
        console.log('CHECK_HC_RETURN_JSON', JSON.stringify(result));
    } catch (e) {
        console.log('CHECK_HC_RETURN_JSON_ERROR', e && e.message ? e.message : String(e));
    }

    // If execute_async_script was used, the last argument is a callback function.
    try {
        const possibleCallback = (typeof arguments !== 'undefined') ? arguments[arguments.length - 1] : null;
        if (typeof possibleCallback === 'function') {
            // deliver the full object via the async callback
            possibleCallback(result);
            // no explicit return needed when using async callback
        } else {
            // synchronous return (execute_script)
            return result;
        }
    } catch (e) {
        // Fallback to returning the object in case of any error
        return result;
    }

} catch (error) {
    return { 
        success: false, 
        message: 'Error: ' + error.toString(), 
        cryptoDetection: cryptoDetection, // Now this is available
        logs: logs 
    };
}