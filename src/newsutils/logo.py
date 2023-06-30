import os
from urllib.parse import urljoin


def parse_logo(response, name='logo'):
    """
    Parse logo url from response.
    Matches substring `name` in @src, @class, @title or @alt attributes
    of <a>, <img>.
    """

    def clean_url(url):
        return urljoin(response.url, url)

    # List possible logo extensions
    ext_list = [".png", ".gif", ".jpg", ".tif", ".tiff", ".bmp", ".svg"]

    # Extract the Home Page Address or Website First Page Address
    str_url = str(response.url).lower()
    parts = len(str_url.split("/"))
    if len(str_url.split("/")[parts - 1]) == 0:
        homepage = str_url.split("/")[parts - 2]
    else:
        homepage = str_url.split("/")[parts - 1]
    print(homepage)

    img_url_list = []
    url_list = []
    case_list = []
    found = False

    # Case 1: when <a> contains <img> with logo substring in its @src
    for tag_a in response.xpath('//a'):
        for tag_img in tag_a.xpath('.//img'):
            img_url = str(tag_img.xpath('@src').get())
            img_url = clean_url(img_url)
            ind = img_url.find(name)
            if ind > 0:
                found = True
                img_url_list.append(img_url)
                url_list.append(str_url)
                case_list.append('1')

    # Case 2: when <div> contains <img>  with logo substring in its @src
    if not found:
        for tag_div in response.xpath('//div'):
            for tag_img in tag_div.xpath('.//img'):
                img_url = str(tag_img.xpath('@src').get())
                img_url = clean_url(img_url)
                ind = img_url.find(name)
                if ind > 0:
                    found = True
                    img_url_list.append(img_url)
                    url_list.append(str_url)
                    case_list.append('2')

    # Case 3: when <a> contains @href as home page address or index. and
    # <img> with possible file extension as like (.png, .gif, .jpg etc) and
    # logo substring in its @class or @title or @alt
    if not found:
        for tag_a in response.xpath('//a'):
            a_href = str(tag_a.xpath('@href').get())
            a_href = clean_url(a_href)
            if a_href[:6] == str("index.") or a_href == homepage:
                for tag_img in tag_a.xpath('.//img'):
                    img_url = str(tag_img.xpath('@src').get())
                    img_url = clean_url(img_url)
                    img_name, img_ext = os.path.splitext(img_url)

                    tag_class = str(tag_img.xpath('@class').get()).lower().strip()
                    title = str(tag_img.xpath('@title').get()).lower().strip()
                    alt = str(tag_img.xpath('@alt').get()).lower().strip()

                    if img_ext in ext_list or tag_class.find(name) > 0 or title.find(name) > 0 or \
                            alt.find(name) > 0:
                        found = True
                        img_url_list.append(img_url)
                        url_list.append(str_url)
                        case_list.append('3')

    data = {'img_url_list': img_url_list, 'url_list': url_list, 'case_list': case_list}

    # for div in response.css('div'):
    #     for img in div.xpath('img'):
    #         for attr in img.css('img::attr(src)'):
    #             img_url = str(attr.get()).lower()
    #             ind = img_url.find('logo')
    #             if ind > 0:
    #                 div_list.append(str(div.get()))
    #                 img_list.append(str(img.get()))
    #                 img_url_list.append(str(img_url))
    #                 #print(img_url)
    return data


