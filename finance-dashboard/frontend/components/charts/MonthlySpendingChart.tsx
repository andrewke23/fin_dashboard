'use client';

import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { getMonthlySpending } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Loader2 } from 'lucide-react';

export default function MonthlySpendingChart() {
  const { data, isLoading } = useQuery({
    queryKey: ['monthly_spending'],
    queryFn: getMonthlySpending,
  });

  if (isLoading) {
    return (
      <Card className="col-span-full md:col-span-2 h-[350px] flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </Card>
    );
  }

  // Reverse the data so the oldest month is on the left, newest on the right
  const chartData = data ? [...data].reverse() : [];

  return (
    <Card className="col-span-full md:col-span-2">
      <CardHeader>
        <CardTitle>Monthly Outflow</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-[250px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
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
                tickFormatter={(value) => `$${value}`}
                className="text-xs text-muted-foreground"
              />
              <Tooltip 
                cursor={{ fill: 'hsl(var(--muted) / 0.5)' }}
                contentStyle={{ backgroundColor: 'hsl(var(--card))', borderColor: 'hsl(var(--border))', borderRadius: '8px' }}
                itemStyle={{ color: 'hsl(var(--foreground))' }}
                formatter={(value: unknown) => {
                  // Safely parse the unknown Recharts value into a number
                  const num = typeof value === 'number' ? value : Number(value);
                  return [`$${(num || 0).toFixed(2)}`, 'Total Spent'];
                }}
                labelFormatter={(label) => `Month: ${label}`}
              />
              <Bar dataKey="total" fill="#10b981" radius={[4, 4, 0, 0]} maxBarSize={50} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}