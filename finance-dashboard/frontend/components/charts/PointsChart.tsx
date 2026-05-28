'use client';

import React, { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { getPointsByCard } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Loader2, Award } from 'lucide-react';

interface PointData {
  card: string;
  points: number;
}

export default function PointsChart() {
  const [dateRange, setDateRange] = useState<string>('all');
  const [customStart, setCustomStart] = useState<string>('');
  const [customEnd, setCustomEnd] = useState<string>('');

  // Calculate the actual dates based on the dropdown selection
  const { startDate, endDate } = useMemo(() => {
    if (dateRange === 'all') return { startDate: undefined, endDate: undefined };
    if (dateRange === 'custom') return { startDate: customStart || undefined, endDate: customEnd || undefined };
    
    const today = new Date();
    const end = today.toISOString().split('T')[0]; // Today as YYYY-MM-DD
    
    if (dateRange === 'week') today.setDate(today.getDate() - 7);
    if (dateRange === 'month') today.setMonth(today.getMonth() - 1);
    if (dateRange === '6m') today.setMonth(today.getMonth() - 6);
    if (dateRange === 'year') today.setFullYear(today.getFullYear() - 1);
    
    return { startDate: today.toISOString().split('T')[0], endDate: end };
  }, [dateRange, customStart, customEnd]);

  // Fetch the data (the query key array ensures React Query automatically refetches when dates change)
  const { data, isLoading } = useQuery<PointData[]>({
    queryKey: ['points_by_card', startDate, endDate],
    queryFn: () => getPointsByCard(startDate, endDate),
    staleTime: 1000 * 60 * 5, // Cache for 5 minutes so it stops reloading instantly
  });

  const chartData = data || [];
  const totalPoints = chartData.reduce((sum, item) => sum + item.points, 0);

  // Cool purple gradient colors for the bars
  const colors = ['#9333ea', '#a855f7', '#c084fc', '#d8b4fe', '#e9d5ff'];

  return (
    <Card className="col-span-full md:col-span-1">
      <CardHeader className="flex flex-col space-y-3 pb-2">
        <div className="flex flex-row items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Award className="h-5 w-5 text-purple-500" />
            Points By Card
          </CardTitle>
          <span className="text-sm font-bold text-purple-500">{totalPoints.toLocaleString()} pts</span>
        </div>
        
        {/* Date Filters */}
        <div className="flex flex-col gap-2">
          <Select value={dateRange} onValueChange={setDateRange}>
            <SelectTrigger className="h-8 text-xs bg-secondary border-none">
              <SelectValue placeholder="Select timeframe" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="week">Last Week</SelectItem>
              <SelectItem value="month">Last Month</SelectItem>
              <SelectItem value="6m">Last 6 Months</SelectItem>
              <SelectItem value="year">Last Year</SelectItem>
              <SelectItem value="all">All Time</SelectItem>
              <SelectItem value="custom">Custom Range</SelectItem>
            </SelectContent>
          </Select>

          {/* Show date pickers only if custom is selected */}
          {dateRange === 'custom' && (
            <div className="flex gap-2">
              <input 
                type="date" 
                className="flex-1 h-8 px-2 text-xs rounded-md bg-secondary text-foreground focus:outline-none focus:ring-1 focus:ring-purple-500"
                value={customStart}
                onChange={(e) => setCustomStart(e.target.value)}
              />
              <input 
                type="date" 
                className="flex-1 h-8 px-2 text-xs rounded-md bg-secondary text-foreground focus:outline-none focus:ring-1 focus:ring-purple-500"
                value={customEnd}
                onChange={(e) => setCustomEnd(e.target.value)}
              />
            </div>
          )}
        </div>
      </CardHeader>

      <CardContent>
        <div className="h-[220px] w-full mt-4">
          {isLoading ? (
            <div className="h-full flex items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : chartData.length === 0 ? (
            <div className="h-full flex items-center justify-center text-sm text-muted-foreground">
              No points earned in this timeframe.
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--muted-foreground) / 0.2)" />
                <XAxis 
                  dataKey="card" 
                  tickLine={false} 
                  axisLine={false} 
                  tick={{ fontSize: 11 }}
                  className="text-muted-foreground"
                />
                <YAxis 
                  tickLine={false} 
                  axisLine={false} 
                  tickFormatter={(value) => value >= 1000 ? `${(value / 1000).toFixed(1)}k` : value}
                  className="text-xs text-muted-foreground"
                />
                <Tooltip 
                  cursor={{ fill: 'hsl(var(--muted-foreground) / 0.1)' }}
                  contentStyle={{ backgroundColor: 'hsl(var(--card))', borderColor: 'hsl(var(--border))', borderRadius: '8px' }}
                  itemStyle={{ color: '#a855f7', fontWeight: 'bold' }}
                  formatter={(value: unknown) => {
                    const num = typeof value === 'number' ? value : Number(value);
                    return [`${(num || 0).toLocaleString()} pts`, 'Earned'];
                  }}
                />
                <Bar dataKey="points" radius={[4, 4, 0, 0]}>
                  {chartData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={colors[index % colors.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </CardContent>
    </Card>
  );
}