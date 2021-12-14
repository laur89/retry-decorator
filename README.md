[![PyPI version](https://badge.fury.io/py/retry-deco.svg)](https://badge.fury.io/py/retry-deco)
    
# Retry decorator

## Usage

```
    #!/usr/bin/env python

    import sys
    from retry_decorator import retry, RetryHandler
    
    
    def throw_err(msg):
        print('hello', file=sys.stderr)
        raise Exception('throwing err for {}'.format(msg))
    
    
    def callback(msg):
        print('callback called: {}'.format(msg), file=sys.stderr)
    
    
    @retry(Exception, tries=3, timeout_secs=0.1)
    def test_retry_via_decorator():
        throw_err('retry-via-deco')
    
    
    def test_retry_via_instance():
        cbe = {
            Exception: lambda: callback('retry-via-instance')
        }
        retry(tries=3, callback_by_exception=cbe)(throw_err)('retry-via-instance')


    def test_retry_via_instance2():
        cbe = {
            Exception: lambda: callback('retry-via-instance2')
        }
        RetryHandler(tries=3, callback_by_exception=cbe)(throw_err, 'retry-via-instance2')
    
    
    if __name__ == '__main__':
        try:
            test_retry_via_decorator()
        except Exception as e:
            print('Received the last exception')
    
        try:
            test_retry_via_instance()
        except Exception as e:
            print('Received the last exception')
    
        try:
            test_retry_via_instance2()
        except Exception as e:
            print('Received the last exception')
```


## Building

```
python -m pip install --upgrade build
python3 -m build
```


## Contribute

Best contribute to [upstream](https://github.com/pnpnpn/retry-decorator) project,
but it _might_ be abandoned. Also its defaults will be different from this project,
unless [PR21](https://github.com/pnpnpn/retry-decorator/pull/21) (which is the reason
for this fork) is accepted.

So... it's up to you which project you raise your PR against, but contributions are welcome.


## Credits

This project is a fork of upstream https://github.com/pnpnpn/retry-decorator


## See also

- [PyRetry](https://github.com/Abeautifulsnow/PyRetry)
- [retry_module](https://github.com/adityaprakash-bobby/retry_module)
- [retry2](https://github.com/eSAMTrade/retry)

