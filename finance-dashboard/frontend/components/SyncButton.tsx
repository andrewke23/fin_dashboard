'use client';

import React from 'react';
import { useMutation, useQueryClient, useQuery } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { getInstitutions, syncTransactions } from '@/lib/api';
import { RefreshCw } from 'lucide-react';

export default function SyncButton() {
  const queryClient = useQueryClient();

  // Get linked institutions so we know what IDs to sync
  const { data: institutions } = useQuery({
    queryKey: ['institutions'],
    queryFn: getInstitutions,
  });

  const syncMutation = useMutation({
    mutationFn: async () => {
      if (!institutions || institutions.length === 0) return;
      
      // Sync all linked banks sequentially
      for (const inst of institutions) {
        await syncTransactions(inst.id);
      }
    },
    onSuccess: () => {
      // Invalidate both caches to force the UI to redraw with new rows
      queryClient.invalidateQueries({ queryKey: ['institutions'] });
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
    },
  });

  const hasAccounts = institutions && institutions.length > 0;

  return (
    <Button
      variant="outline"
      size="sm"
      disabled={!hasAccounts || syncMutation.isPending}
      onClick={() => syncMutation.mutate()}
    >
      <RefreshCw className={`h-4 w-4 mr-2 ${syncMutation.isPending ? 'animate-spin' : ''}`} />
      {syncMutation.isPending ? 'Syncing Ledger...' : 'Sync Banks'}
    </Button>
  );
}