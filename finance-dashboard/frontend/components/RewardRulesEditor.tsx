'use client';

import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getInstitutions, updateRewardRules } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Plus, Trash2, Save, Loader2 } from 'lucide-react';
import { Institution, Account } from '@/types';

// Standard Plaid categories for the dropdown
const STANDARD_CATEGORIES = [
  "FOOD_AND_DRINK", "TRAVEL", "TRANSPORTATION", 
  "GENERAL_MERCHANDISE", "ENTERTAINMENT", "PERSONAL_CARE", 
  "BILLS_AND_UTILITIES", "SHOPPING"
];

export default function RewardRulesEditor() {
  const queryClient = useQueryClient();
  const [selectedAccountId, setSelectedAccountId] = useState<string>('');
  const [baseMultiplier, setBaseMultiplier] = useState<number>(1.0);
  const [categories, setCategories] = useState<{ category: string; multiplier: number }[]>([]);

  // Fetch accounts
  const { data: institutions, isLoading } = useQuery<Institution[]>({
    queryKey: ['institutions'],
    queryFn: getInstitutions,
  });

  const flatAccounts = institutions?.flatMap(inst => inst.accounts) || [];

  // Update state actively on user interaction rather than passively via useEffect
  const handleAccountChange = (accountId: string) => {
    setSelectedAccountId(accountId);
    
    const account = flatAccounts.find(a => a.id === accountId);
    if (account) {
      const rules = account.reward_rules || { base: 1.0, categories: {} };
      setBaseMultiplier(rules.base || 1.0);
      
      const catsArray = Object.entries(rules.categories || {}).map(([key, val]) => ({
        category: key,
        multiplier: Number(val),
      }));
      setCategories(catsArray);
    }
  };

  // Save Mutation
  const saveMutation = useMutation({
    mutationFn: (accountId: string) => {
      // Convert the array back into the JSON object format the backend expects
      const categoriesObj: Record<string, number> = {};
      categories.forEach(c => {
        if (c.category) categoriesObj[c.category] = Number(c.multiplier);
      });

      const payload = {
        base: Number(baseMultiplier),
        categories: categoriesObj,
      };
      return updateRewardRules(accountId, payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['institutions'] });
      alert("Rules saved successfully! Sync your banks to apply these rules to new transactions.");
    }
  });

  if (isLoading) return <div className="text-sm text-muted-foreground">Loading accounts...</div>;

  return (
    <Card className="col-span-full md:col-span-1">
      <CardHeader>
        <CardTitle>Credit Card Multipliers</CardTitle>
        <CardDescription>Configure point earning rules per card.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        
        {/* Account Selector */}
        <div className="space-y-2">
          <label className="text-xs font-semibold text-muted-foreground">Select Card</label>
          <Select value={selectedAccountId} onValueChange={handleAccountChange}>
            <SelectTrigger className="w-full">
              <SelectValue placeholder="Choose an account..." />
            </SelectTrigger>
            <SelectContent>
              {flatAccounts.map((acc: Account) => (
                <SelectItem key={acc.id} value={acc.id}>
                  {acc.name} {acc.mask ? `(..${acc.mask})` : ''}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {selectedAccountId && (
          <div className="space-y-6 pt-4 border-t border-muted">
            
            {/* Base Multiplier */}
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Base Multiplier (Everything Else)</span>
              <div className="flex items-center space-x-2">
                <input 
                  type="number" 
                  step="0.1"
                  value={baseMultiplier}
                  onChange={(e) => setBaseMultiplier(parseFloat(e.target.value))}
                  className="w-20 bg-secondary rounded-md px-3 py-1 text-sm text-right focus:outline-none focus:ring-1 focus:ring-ring"
                />
                <span className="text-sm text-muted-foreground font-mono">x</span>
              </div>
            </div>

            {/* Category Multipliers */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">Category Bonuses</span>
                <Button 
                  variant="outline" 
                  size="sm" 
                  className="h-7 text-xs"
                  onClick={() => setCategories([...categories, { category: '', multiplier: 2.0 }])}
                >
                  <Plus className="h-3 w-3 mr-1" /> Add Rule
                </Button>
              </div>

              {categories.map((cat, index) => (
                <div key={index} className="flex items-center space-x-2">
                  <Select 
                    value={cat.category} 
                    onValueChange={(val) => {
                      const newCats = [...categories];
                      newCats[index].category = val;
                      setCategories(newCats);
                    }}
                  >
                    <SelectTrigger className="flex-1 h-9">
                      <SelectValue placeholder="Select Category" />
                    </SelectTrigger>
                    <SelectContent>
                      {STANDARD_CATEGORIES.map(c => (
                        <SelectItem key={c} value={c}>{c.replace(/_/g, ' ')}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  
                  <input 
                    type="number" 
                    step="0.1"
                    value={cat.multiplier}
                    onChange={(e) => {
                      const newCats = [...categories];
                      newCats[index].multiplier = parseFloat(e.target.value) || 0;
                      setCategories(newCats);
                    }}
                    className="w-16 h-9 bg-secondary rounded-md px-2 text-sm text-right focus:outline-none focus:ring-1 focus:ring-ring"
                  />
                  <span className="text-sm text-muted-foreground font-mono pr-2">x</span>

                  <Button 
                    variant="ghost" 
                    size="icon" 
                    className="h-9 w-9 text-muted-foreground hover:text-red-500"
                    onClick={() => setCategories(categories.filter((_, i) => i !== index))}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              ))}
            </div>

            {/* Save Button */}
            <Button 
              className="w-full" 
              disabled={saveMutation.isPending}
              onClick={() => saveMutation.mutate(selectedAccountId)}
            >
              {saveMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
              Save Ruleset
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}