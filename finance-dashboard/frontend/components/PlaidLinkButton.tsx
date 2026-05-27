'use client';

import React, { useEffect, useState } from 'react';
import { usePlaidLink, PlaidLinkOptions, PlaidLinkOnSuccess } from 'react-plaid-link';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { createLinkToken, exchangePublicToken } from '@/lib/api';
import { PlusCircle } from 'lucide-react';

export default function PlaidLinkButton() {
  const [linkToken, setLinkToken] = useState<string | null>(null);
  const [isLoadingToken, setIsLoadingToken] = useState(false);
  const queryClient = useQueryClient();

  // Fetch link token only if we don't have one and aren't already loading
  useEffect(() => {
    if (linkToken || isLoadingToken) return;

    const fetchToken = async () => {
      setIsLoadingToken(true);
      try {
        const token = await createLinkToken();
        setLinkToken(token);
      } catch (error) {
        console.error("Error fetching link token:", error);
      } finally {
        setIsLoadingToken(false);
      }
    };
    fetchToken();
  }, [linkToken, isLoadingToken]);

  const exchangeMutation = useMutation({
    mutationFn: async ({ publicToken, institutionName }: { publicToken: string, institutionName: string }) => {
      return exchangePublicToken(publicToken, institutionName);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['institutions'] });
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      // Clear token so a fresh one can be generated if they click again
      setLinkToken(null);
    },
  });

  const onSuccess: PlaidLinkOnSuccess = async (publicToken: string, metadata) => {
    const institutionName = metadata.institution?.name || 'Unknown Institution';
    exchangeMutation.mutate({ publicToken, institutionName });
  };

  const config: PlaidLinkOptions = {
    token: linkToken || '', // Fallback to avoid empty strings compiling weirdly
    onSuccess,
  };

  const { open, ready } = usePlaidLink(config);

  return (
    <Button 
      onClick={() => open()} 
      disabled={!ready || !linkToken || exchangeMutation.isPending}
    >
      <PlusCircle className="mr-2 h-4 w-4" />
      {exchangeMutation.isPending ? 'Linking...' : 'Link Account'}
    </Button>
  );
}