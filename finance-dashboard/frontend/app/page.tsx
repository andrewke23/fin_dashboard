'use client';

import { useQuery } from '@tanstack/react-query';
import { getInstitutions } from '@/lib/api';
import PlaidLinkButton from '@/components/PlaidLinkButton';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Building2, Wallet, Trash2 } from 'lucide-react';
import { Institution, Account } from '@/types';
import MonthlySpendingChart from '@/components/charts/MonthlySpendingChart';
import CategoryPieChart from '@/components/charts/CategoryPieChart';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { unlinkInstitution } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { toggleAccountActive } from '@/lib/api';
import PointsChart from '@/components/charts/PointsChart';
import RewardRulesEditor from '@/components/RewardRulesEditor';

export default function DashboardPage() {
  const queryClient = useQueryClient();
  
  const { data: institutions, isLoading, error } = useQuery({
    queryKey: ['institutions'],
    queryFn: getInstitutions,
  });

  const toggleMutation = useMutation({
    mutationFn: toggleAccountActive,
    onSuccess: () => {
      // Force all queries to instantly reload and read from the updated database state
      queryClient.invalidateQueries({ queryKey: ['institutions'] });
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['category_breakdown'] });
      queryClient.invalidateQueries({ queryKey: ['monthly_spending'] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: unlinkInstitution,
    onSuccess: () => {
      // Instantly refresh the dashboard after deletion
      queryClient.invalidateQueries({ queryKey: ['institutions'] });
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['category_breakdown'] });
      queryClient.invalidateQueries({ queryKey: ['monthly_spending'] });
    },
  });

  if (isLoading) return <div className="p-8">Loading dashboard...</div>;
  if (error) return <div className="p-8 text-red-500">Error loading data. Is the backend running?</div>;

  return (
    <div className="space-y-8">
      {/* Dashboard Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-4xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground mt-2">Welcome to your local finance hub.</p>
        </div>
        <PlaidLinkButton />
      </div>
      {institutions && institutions.length > 0 && (
        <div className="grid gap-4 md:grid-cols-3 mt-8">
          <MonthlySpendingChart />
          <CategoryPieChart />
          <PointsChart />
          <RewardRulesEditor />
        </div>
      )}
      {/* --- Institutions Grid --- */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {institutions?.map((inst: Institution) => (
          <Card key={inst.id}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <div className="flex items-center space-x-2">
                <Building2 className="h-4 w-4 text-muted-foreground" />
                <CardTitle className="text-sm font-medium">
                  {inst.institution_name}
                </CardTitle>
              </div>
              <Button 
                variant="ghost" 
                size="icon" 
                className="h-8 w-8 text-muted-foreground hover:text-red-500 hover:bg-red-500/10"
                disabled={deleteMutation.isPending}
                onClick={() => {
                  if (window.confirm(`Are you sure you want to unlink ${inst.institution_name}? All local data for this bank will be deleted.`)) {
                    deleteMutation.mutate(inst.id);
                  }
                }}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {inst.accounts.length} Accounts
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                Last synced: {inst.last_sync ? new Date(inst.last_sync).toLocaleDateString() : 'Never'}
              </p>
              
              <div className="mt-4 space-y-3">
                {inst.accounts.map((acc: Account) => (
                  <div key={acc.id} className={`flex items-center justify-between text-sm ${!acc.is_active ? 'opacity-50 grayscale' : ''}`}>
                    <div className="flex items-center space-x-3">
                      <Switch 
                        checked={acc.is_active !== false} // defaults to true
                        onCheckedChange={() => toggleMutation.mutate(acc.id)}
                        disabled={toggleMutation.isPending}
                      />
                      <span className="text-muted-foreground">
                        {acc.name} {acc.mask ? `(...${acc.mask})` : ''}
                      </span>
                    </div>
                    <span className="font-medium">${(acc.current_balance || 0).toFixed(2)}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        ))}

        {/* Empty State */}
        {institutions?.length === 0 && (
          <div className="col-span-full p-8 text-center border rounded-lg border-dashed">
            <Wallet className="mx-auto h-8 w-8 text-muted-foreground mb-4" />
            <h3 className="text-lg font-medium">No accounts linked</h3>
            <p className="text-sm text-muted-foreground mt-1 mb-4">
              Connect your first financial institution to get started.
            </p>
            <PlaidLinkButton />
          </div>
        )}
      </div>

      
    </div>
  );
}