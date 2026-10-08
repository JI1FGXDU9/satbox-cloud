def timestamp(value):
    return value.isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def display(prediction):
    print('All timestamps UTC; AZ: north=0 degrees, east=90 degrees')
    print('AOS UTC | AOS AZ | MAX UTC | MAX EL | LOS UTC | LOS AZ | duration(s)')
    for p in prediction.passes:
        print(f'{timestamp(p.aos)} | {p.aos_az_deg:.3f} | '
              f'{timestamp(p.maximum_at)} | {p.maximum_el_deg:.3f} | '
              f'{timestamp(p.los)} | {p.los_az_deg:.3f} | {p.duration_seconds:.3f}')
    print(f'Complete passes: {len(prediction.passes)}')
    if prediction.visible_at_start:
        print('NOTE: Already above horizon at start; initial incomplete pass omitted.')
    if prediction.visible_at_end:
        print('NOTE: Still above horizon at end; final incomplete pass omitted.')
