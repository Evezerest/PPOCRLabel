#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Authors: zhulingfeng01@baidu.com
Date: 2020-8-31
"""
import sys,os
import base64
import json
import os
from urllib.parse import urlparse
import urllib.request
import base64
# reload(sys)
# sys.setdefaultencoding('utf-8')
ENCODING = 'utf-8'

def get_img_base64(img_file):
    with open(img_file, 'rb') as infile:
        s = infile.read()
        return base64.b64encode(s).decode(ENCODING)


def predict(url, appcode, img_base64, kv_configure):
        param = {}
        param['image'] = img_base64
        if kv_configure is not None:
            param['configure'] = json.dumps(kv_configure)
        body = json.dumps(param)
        data = bytes(body, "utf-8")

        headers = {'Authorization' : 'APPCODE %s' % appcode}
        request = urllib.request.Request(url = url, headers = headers, data = data)
        try:
            response = urllib.request.urlopen(request, timeout = 10)
            return response.code, response.headers, response.read()
        except urllib.request.HTTPError as e:
            return e.code, e.headers, e.read()


def demo(img_file):
    # appcode = '8447a30f98b94fb39271a7b7e7f4f3f3'
    # appcode = '97476bc700b54f0697a7c19320a5b480'
    appcode = '7b1dc865597740c18ee91fdfd73b3046'
    # url = 'https://ocrapi-advanced.taobao.com/ocrservice/advanced'
    url = 'http://tysbgpu.market.alicloudapi.com/api/predict/ocr_general' #'http://dm-51.data.aliyun.com/rest/160601/ocr/ocr_idcard.json'#
    # img_file = 'E:\Paddle/510-test/OCR增补测试-png- (23).png' #'图片文件路径/图片url'
    # configure = {'side':'face'}
    #如果没有configure字段，configure设为None
    configure = {"min_size" : 16, # 图片中文字的最小高度，单位像素
            "output_prob" : True, # 是否输出文字框的概率
            "output_keypoints": True,          # 是否输出文字框角点
            "skip_detection": False,             # 是否跳过文字检测步骤直接进行文字识别
            "without_predicting_direction": False,   # 是否关闭文字行方向预测}
                 }
    img_base64data = get_img_base64(img_file)
    stat, header, content = predict(url, appcode, img_base64data, configure)
    if stat != 200:
        print('Http status code: ', stat)
        print('Error msg in header: ', header['x-ca-error-message'] if 'x-ca-error-message' in header else '')
        print('Error msg in body: ', content)
        exit()
    result_str = content

    print(result_str.decode(ENCODING))
    #result = json.loads(result_str)

    return result_str.decode(ENCODING)

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


if __name__ == '__main__':
    # imgdir = 'E:\Paddle/all-sum-510' #'E:\Paddle/510-test'
    # # outputfile = './result_advance.csv'
    # raw_outputfile = './result_3.0raw.txt' # 原始输出
    # outputfile = './result_3.0.txt' # 处理后输出
    # labelfile = 'E:\Paddle/system_test_set_label_list_310.txt' # 只测这310张
    # # labelfile = 'E:\Paddle\Project\OCR_EXAMPLE-master\python3/result.txt'
    # num = 0
    # test_dic = getlabel(labelfile) # 全部样本
    # old_test_dic = getlabel(outputfile)  # 已测样本
    #
    # with open(raw_outputfile, 'a+', encoding='utf-8') as raw_f: #
    #     with open(outputfile, 'a+', encoding='utf-8') as process_f:  #
    #         for files in os.listdir(imgdir):
    #             # if num == 1: break
    #             # a = files[:-3] + 'jpg'
    #             if files in test_dic and files not in old_test_dic:
    #                 result = demo(os.path.join(imgdir, files)) # result是个str
    #                 a = result.replace('true', 'True')
    #                 result_dic = eval(a)
    #                 # Keypoints 变为points 然后几个坐标放一起
    #                 if len(result_dic)>2:
    #                     trans_list = []
    #                     for box in result_dic['ret']: # 每个box都是dict 仍然要组成dict
    #                         for k in box.keys(): # each box
    #                             if k == "keypoints":
    #                                 point = [[int(box[k][i]['x']), int(box[k][i]['y'])] for i in range(4)]
    #                             elif k =='word':
    #                                 word = box[k]
    #                         trans_dic = {"transcription": word, "points": point}
    #                         trans_list.append(trans_dic)
    #
    #                     process_f.write('all-sum-510/'+ files + '\t')
    #                     process_f.write(json.dumps(trans_list, ensure_ascii=False) + '\n')#str(trans_list)
    #                 else: # 没有检测到文字
    #                     process_f.write('all-sum-510/' + files + '\t')
    #                     process_f.write('[]' + '\n')
    #
    #                 raw_f.write(files+'\t')
    #                 raw_f.write(result + '\n')
    #
    #                 num +=1
    #     process_f.close()
    # raw_f.close()
    # print('total test files: ', num)

    demo('E:\Paddle\pic/ads.jpg')
