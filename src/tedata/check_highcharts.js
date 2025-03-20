const logs = [];
console.log = function(msg) { logs.push(msg); };

try {
    // Check if Highcharts exists
    if (typeof Highcharts === 'undefined') {
        return { success: false, message: 'Highcharts not found', logs: logs };
    }
    
    // Find charts in the page
    if (!Highcharts.charts || Highcharts.charts.length === 0) {
        return { success: false, message: 'No Highcharts instances found', logs: logs };
    }
    
    // Find a valid chart
    const chart = Highcharts.charts.find(c => c && c.series && c.series.length > 0);
    if (!chart) {
        return { success: false, message: 'No valid chart with series found', logs: logs };
    }
    
    // Get basic chart info
    const info = {
        seriesCount: chart.series.length,
        pointsCount: chart.series[0]?.points?.length || 0,
        xAxisType: chart.xAxis[0]?.options?.type,
        chartType: chart.options?.chart?.type,
        hasTooltip: !!chart.tooltip
    };
    
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
    }
    
    return { 
        success: true, 
        message: 'Highcharts API accessed successfully', 
        info: info,
        seriesData: seriesData,
        logs: logs 
    };
} catch (error) {
    return { 
        success: false, 
        message: 'Error: ' + error.toString(), 
        logs: logs 
    };
}