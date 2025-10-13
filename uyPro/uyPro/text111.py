import translators


def translate_segment_bing(segment, proxies):
    return translators.translate_text(segment, translator='bing', to_language='zh', proxies=proxies, timeout=30)


if __name__ == '__main__':
    p = 'socks5://eff7b75e:c52895c2@154.18.225.1:13894'
    proxies = {protocol: p for protocol in ['http', 'https']}
    print(proxies)
    text = 'Philippines, Japan Pledge Further Defense Cooperation Amid South China Sea Spats'
    translated5 = translate_segment_bing(text, proxies)
    print('bing:')
    print(translated5)

