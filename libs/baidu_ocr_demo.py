# encoding:utf-8

import requests
import base64
import os
import json

'''
通用文字识别
'''
def getlabel(labelfile):
    # extract the file name in the first column of labelfile
    test_dic = []
    with open(labelfile, 'r', encoding='utf-8') as label: #
        # line = label.readline() # 按行读取方式
        # while line:
        #     imgname = line.decode('utf8', 'ignore')
        #     if imgname[0][-3:] != 'jpg':  # 部分文件命名中有空格jason
        #         comb = imgname[0]+' '+imgname[1]
        #         imgname[0] = comb
        #     test_dic.append(imgname[0].split('/')[1])
        #     line = label.readline()
        for l in label:
            # if "all-sum-510/OCR测试-竖排-(1).png" in l: # 测试
            #     print(l)
            imgname = l.split()
            # a=imgname[0][-3:]
            # if imgname[0][-3:] != 'jpg': # 部分文件命名中有空格
            #     comb = imgname[0]+' '+imgname[1]
            #     imgname[0] = comb
            if imgname[1][0] == '(':  # 部分文件命名中有空格
                comb = imgname[0] + ' ' + imgname[1]
                imgname[0] = comb
            test_dic.append(imgname[0].split('/')[1])
    return test_dic

def demo(img_file):
    # request_url = "https://aip.baidubce.com/rest/2.0/ocr/v1/general" # 标准版带位置
    request_url = "https://aip.baidubce.com/rest/2.0/ocr/v1/accurate" # 高精度版
    # 二进制方式打开图片文件
    f = open(img_file, 'rb')
    img = base64.b64encode(f.read())

    params = {"image": img,
              #"recognize_granularity": "big",
              "vertexes_location": 'true'}
    access_token = '24.b04028421ef499d57673a7ef5ecdec70.2592000.1601629430.282335-22505535'
    # access_token = '24.7e1ebcf13183e7c2e97692485807757b.2592000.1601802660.282335-22554267'
    # access_token = '24.9feb38c3dd24a55cd7f2f72e780c0cae.2592000.1601802703.282335-22554235'
    # access_token = '24.e82a87d4ae69d02dfc0545df9e66c994.2592000.1601990033.282335-22570077'

    request_url = request_url + "?access_token=" + access_token
    headers = {'content-type': 'application/x-www-form-urlencoded'}
    response = requests.post(request_url, data=params, headers=headers)
    if response:
        print(response.json())

    return response.json()

def getAccessKey():
    # client_id 为官网获取的AK， client_secret 为官网获取的SK
    # host = 'https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id=xWUY3C0SctodnKo7zoabOMSR&client_secret=FIhGUEUP7GmtotzaW6Ct3jXeWjhXCriP'
    # host = 'https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id=FHdeqSirVtZ1ui7cAmQ22uwF&client_secret=SO45YQyq1iGxHPIF8twpNHraZGt43gDp'
    host = 'https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id=zgbzjB9DCurnkaoa97BRemDV&client_secret=ElIlM7jk2exZ0bs76yWBtUhbwm2YnBGW' # huage
    # host = 'https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id=FHdeqSirVtZ1ui7cAmQ22uwF&client_secret=SO45YQyq1iGxHPIF8twpNHraZGt43gDp'
    # host = 'https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id=FHdeqSirVtZ1ui7cAmQ22uwF&client_secret=SO45YQyq1iGxHPIF8twpNHraZGt43gDp'

    response = requests.get(host)
    if response:
        print(response.json())

def convert4p(loc):
    # convert top-left to 4 point
    return [[loc[0], loc[1]], [loc[0]+loc[2], loc[1]], [loc[0]+loc[2], loc[1]+loc[3]], [loc[0],loc[1]+loc[3]]]


def ocr_main(imgdir, ):
    imgdir = 'E:\Paddle/all-sum-510'  # 'E:\Paddle/510-test'
    # outputfile = './result_advance.csv'

    # 高精度版
    raw_outputfile = './result_baidu_acc_raw.txt'  # 原始输出
    outputfile = './result_baidu_acc.txt'  # 处理后输出

    # 标准版：
    # raw_outputfile = './result_baidu1_raw.txt'  # 原始输出
    # outputfile = './result_baidu1.txt'  # 处理后输出

    labelfile = 'E:\Paddle/system_test_set_label_list_310.txt'  # 只测这310张
    # labelfile = 'E:\Paddle\Project\OCR_EXAMPLE-master\python3/result.txt'
    num = 0
    test_dic = getlabel(labelfile)  # 全部样本
    old_test_dic = getlabel(outputfile)  # 已测样本

    with open(raw_outputfile, 'a+', encoding='utf-8') as raw_f:  #
        with open(outputfile, 'a+', encoding='utf-8') as process_f:  #
            for files in os.listdir(imgdir):
                # if num == 1: break
                if files in test_dic and files not in old_test_dic:  # 是否排除已测数据
                    # print(files)
                    result = demo(os.path.join(imgdir, files))  # result是个str
                    # a = result.replace('true', 'True')
                    # result_dic = eval(result)
                    # Keypoints 变为points 然后几个坐标放一起
                    try:
                        if len(result['words_result']) > 0:
                            trans_list = []
                            for box in result['words_result']:  # 每个box都是dict 仍然要组成dict
                                for k in box.keys():  # each box
                                    if k == "vertexes_location":
                                        # loc = [v for v in box[k].values()]
                                        # point = convert4p(loc)
                                        point = [[int(box[k][i]['x']), int(box[k][i]['y'])] for i in range(4)]
                                    elif k == 'words':
                                        word = box[k]
                                trans_dic = {"transcription": word, "points": point}
                                trans_list.append(trans_dic)
                            process_f.write('all-sum-510/' + files + '\t')
                            process_f.write(json.dumps(trans_list, ensure_ascii=False) + '\n')  # str(trans_list)
                        else:  # 没有检测到文字
                            process_f.write('all-sum-510/' + files + '\t')
                            process_f.write('[]' + '\n')

                    except:
                        pass

                    raw_f.write(files + '\t')
                    raw_f.write(str(result) + '\n')

                    num += 1
        process_f.close()
    raw_f.close()
    print('total test files: ', num)


if __name__ == '__main__':

    demo('E:\Paddle\pic/ads.jpg')