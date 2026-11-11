import { Stack, Title } from '@mantine/core';
import { IconCoin } from '@tabler/icons-react';
import { observer } from 'mobx-react-lite';
import { useEffect } from 'react';

import { EmptyState, ErrorState, LoadingState } from '../../components/StateViews';
import { PeriodNavigator } from '../../components/PeriodNavigator';
import { currentMonthStart, formatMonth } from '../../lib/time';
import { usePayStore } from '../../stores/StoreContext';
import { PayBreakdown } from '../pay/PayBreakdown';

/** The signed-in person's pay for a month (product-definition §5.4). */
export const MyPay = observer(function MyPay() {
  const store = usePayStore();

  useEffect(() => {
    void store.loadPay();
  }, [store]);

  let body;
  if (store.payStatus === 'idle' || store.payStatus === 'loading') {
    body = <LoadingState rows={3} />;
  } else if (store.payStatus === 'error') {
    body = <ErrorState message={store.payError ?? ''} onRetry={() => void store.reloadPay()} />;
  } else if (store.pay && (store.hasDays || store.pay.open_entries > 0)) {
    body = <PayBreakdown pay={store.pay} />;
  } else {
    body = (
      <EmptyState
        icon={IconCoin}
        title="No pay yet this month"
        description={`There are no time entries in ${formatMonth(store.monthStart)}.`}
      />
    );
  }

  return (
    <Stack gap="lg">
      <Title order={1}>My pay</Title>
      <PeriodNavigator
        label={formatMonth(store.monthStart)}
        previousLabel="Previous month"
        nextLabel="Next month"
        onPrevious={() => void store.goToMonth(-1)}
        onNext={() => void store.goToMonth(1)}
        resetLabel={store.monthStart === currentMonthStart() ? undefined : 'This month'}
        onReset={() => void store.goToCurrentMonth()}
      />
      {body}
    </Stack>
  );
});
