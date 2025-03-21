// Function to export series data as CSV
function exportSeriesCSV(seriesIndex = 0) {
    const chart = Highcharts.charts.find(c => c && c.series && c.series.length > 0);
    if (!chart || !chart.series || !chart.series[seriesIndex]) {
        return "No valid chart or series found";
    }
    
    const series = chart.series[seriesIndex];
    const csvRows = ["date,value"];
    
    series.points.forEach(p => {
        const date = new Date(p.x).toISOString().split('T')[0];
        csvRows.push(`${date},${p.y}`);
    });
    
    const csv = csvRows.join('\n');
    console.log(csv);
    
    // Create downloadable link (optional)
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.setAttribute('hidden', '');
    a.setAttribute('href', url);
    a.setAttribute('download', `${series.name.replace(/\s+/g, '_')}.csv`);
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    
    return `Exported ${series.points.length} data points from "${series.name}"`;
}

// Export the first series
exportSeriesCSV(0);