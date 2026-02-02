# git sublog

- important refs:
  - starting
  - HEAD-ref
  - comparing

assumption is that starting should be ancestor of bot HEAD and comparing

- colors:
  - green: starting..HEAD-ref
  - red: HEAD-ref..comparing
  - blue-bg is tricky: 
    - it gives a hint that:
      - parent moduel comparing-ref is not bumped to newest version of moddule
      - parent module HEAD-ref is not bumped to newest version of your module