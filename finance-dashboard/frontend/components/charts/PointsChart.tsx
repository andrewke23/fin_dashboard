'use client';

import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { getPointsByMonth } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Loader2, Award } from 'lucide-react';

export default function PointsChart() {
  const { data, isLoading } = useQuery({
    queryKey: ['points_by_month'],
    queryFn: getPointsByMonth,
  });

  if (isLoading) {
    return (
      <Card className="col-span-full md:col-span-1 h-[350px] flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </Card>
    );
  }

  // Reverse the data so the timeline flows from left (oldest) to right (newest)
  const chartData = data ? [...data].reverse() : [];
  
  // Calculate the total points earned across all time for the header
  const totalPoints = chartData.reduce((sum, item) => sum + item.points, 0);

  return (
    <Card className="col-span-full md:col-span-1">
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="flex items-center gap-2">
          <Award className="h-5 w-5 text-purple-500" />
          Points Earned
        </CardTitle>
        <span className="text-sm font-bold text-purple-500">{totalPoints.toLocaleString()} pts</span>
      </CardHeader>
      <CardContent>
        <div className="h-[250px] w-full mt-4">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <defs>
                {/* This creates the smooth fading gradient beneath the line */}
                <linearGradient id="colorPoints" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#a855f7" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="#a855f7" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--muted-foreground) / 0.2)" />
              <XAxis 
                dataKey="month" 
                tickLine={false} 
                axisLine={false} 
                tickFormatter={(value) => {
                  const date = new Date(value + '-01');
                  return date.toLocaleDateString('en-US', { month: 'short' });
                }}
                className="text-xs text-muted-foreground"
              />
              <YAxis 
                tickLine={false} 
                axisLine={false} 
                tickFormatter={(value) => 
                  value >= 1000 ? `${(value / 1000).toFixed(1)}k` : value
                }
                className="text-xs text-muted-foreground"
              />
              <Tooltip 
                contentStyle={{ backgroundColor: 'hsl(var(--card))', borderColor: 'hsl(var(--border))', borderRadius: '8px' }}
                itemStyle={{ color: '#a855f7', fontWeight: 'bold' }}
                formatter={(value: unknown) => {
                  const num = typeof value === 'number' ? value : Number(value);
                  return [`${(num || 0).toLocaleString()} pts`, 'Earned'];
                }}
                labelFormatter={(label) => `Month: ${label}`}
              />
              <Area 
                type="monotone" 
                dataKey="points" 
                stroke="#a855f7" 
                strokeWidth={3} 
                fillOpacity={1} 
                fill="url(#colorPoints)" 
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}