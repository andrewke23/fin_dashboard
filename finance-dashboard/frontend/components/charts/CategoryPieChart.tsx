'use client';

import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import { getCategoryBreakdown } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Loader2 } from 'lucide-react';

const COLORS = ['#10b981', '#06b6d4', '#3b82f6', '#8b5cf6', '#ec4899', '#f43f5e', '#f59e0b', '#84cc16'];

// Define the shape of our data so TypeScript allows us to spread it safely
interface CategoryItem {
  category: string;
  total: number;
  transaction_count: number;
  percentage: number;
}

export default function CategoryPieChart() {
  const { data, isLoading } = useQuery({
    queryKey: ['category_breakdown'],
    queryFn: getCategoryBreakdown,
  });

  if (isLoading) {
    return (
      <Card className="col-span-full md:col-span-1 h-[350px] flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </Card>
    );
  }

  // Format categories nicely for display using our new interface
  const chartData = data?.data.map((item: CategoryItem) => ({
    ...item,
    displayCategory: item.category.replace(/_/g, ' ').toLowerCase(),
  })) || [];

  return (
    <Card className="col-span-full md:col-span-1">
      <CardHeader>
        <CardTitle>Spending by Category</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-[250px] w-full relative">
          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
            <span className="text-2xl font-bold text-foreground">
              ${data?.total_spending.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
            </span>
            <span className="text-xs text-muted-foreground">Total</span>
          </div>
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={chartData}
                cx="50%"
                cy="50%"
                innerRadius={70}
                outerRadius={90}
                paddingAngle={2}
                dataKey="total"
                nameKey="displayCategory"
                stroke="none"
              >
                {chartData.map((entry: CategoryItem, index: number) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip 
                contentStyle={{ backgroundColor: 'hsl(var(--card))', borderColor: 'hsl(var(--border))', borderRadius: '8px', textTransform: 'capitalize' }}
                itemStyle={{ color: 'hsl(var(--foreground))' }}
                formatter={(value: unknown, name: unknown) => {
                  // Safely parse the unknown Recharts value into a number
                  const num = typeof value === 'number' ? value : Number(value);
                  // Return the exact dynamic category name instead of the static "Spent" string
                  return [`$${(num || 0).toFixed(2)}`, String(name)];
                }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}