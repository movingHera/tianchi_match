import os
import PIL
import time
import datetime
import string
import math
import random
from multiprocessing import Pool
from PIL import Image
from readDataParallel import *
import numpy as np
import scipy as sp 
import matplotlib.pyplot as plt
import matplotlib as mpl
from operator import itemgetter  
THEAD_NUM=16#进程数
SEPARATOR_1=' '     #空格分隔符
SEPARATOR_2=','     #以‘，’为分隔符
SEPARATOR_3=';'     #以‘;’为分隔符
MATCH_SET_FILENAME='dim_fashion_match_sets.txt' #穿衣搭配套餐
ITEMS_FILENAME='dim_items.txt'  #商品信息表：dim_items
USER_BUY_HISTORY='user_bought_history.txt'  #用户历史行为表：user_bought_history
RESULT_FILENAME='fm_submissions.txt' #存储每个商品的推荐结果
TEST_IITEMS='test_items.txt'
SPLIT_FOLD_NAME='SPLIT'
SPLIT_NUM=1000

### 读取达人推荐搭配
def readMatchSet(filename):
    fp_match_set=open(filename,'r')
    MatchSet={}
    countLine=0     
    for line in fp_match_set.readlines():                   
        countLine=countLine+1
        coll_id,item_list=line.split(SEPARATOR_1)   #以空格作为分割符号
        detail_item=item_list.split(SEPARATOR_3)    #以‘;’为分隔符
        detain_item_list=[]
        for item_1 in detail_item:
            item_2= item_1.split(SEPARATOR_2)     #以‘，’为分隔符
            item_2_list=[]
            for item in item_2:     
                item_2_list.append(string.atoi(item))     #转化为整形
            detain_item_list.append(item_2_list) 
        MatchSet[string.atoi(coll_id)]=detain_item_list
    fp_match_set.close()
    return MatchSet

##删除列表中所有item条目
def removeAllSame(L,item):
    M=[]
    for i in range(0,len(L)):
        if(L[i]!=item):
            M+=[L[i]]
    return M       
###计算两个list之间的相似度
def similarFactor(List1,List2):
    tmpDic1={}  
    tmpDic2={}
    coutSame=0
    cout1=0
    cout2=0
    for i in List1:
        if tmpDic1.has_key(i)==False:
            tmpDic1[i]=1
            cout1+=1
   
    for j in List2:
        if tmpDic1.has_key(j)==True:
            coutSame+=1
            tmpDic1.pop(j)
        if tmpDic2.has_key(j)==False:
            tmpDic2[j]=1
            cout2+=1
    
    if (cout1+cout2)==0:
        return 0.0
    else:
        return coutSame*2.0/(cout1+cout2)
        
        
    
### 读取所有的商品信息
def readItems(filename):
    time1=time.time()
    print '*****************readItems******************* '
    fp_items=open(filename,'r')
    Items={}
    CategoryItem={} #以类目ID作为key
    ItemCategoryDic={} #以Item为key的字典，可以直接所有item所属的类别
    keyWords={}  #用来存储各个商品分词所对应的商品
    countLine=0
    for line in fp_items.readlines():             
        countLine=countLine+1
        item_id,cat_id,terms=line.split(SEPARATOR_1) #以空格作为分割符号
        item_id=string.atoi(item_id)
        cat_id=string.atoi(cat_id)   
        if(keyWords.has_key(cat_id)==False):
            keyWords[cat_id]={}
        ItemCategoryDic[item_id]=cat_id  #统计item-category
        item_info=[cat_id]
        terms_sp=terms.split(SEPARATOR_2)
        terms_list=[]
        for termStr in terms_sp:
            term=string.atoi(termStr)
            terms_list.append(term)
            if keyWords[cat_id].has_key(term)==False:
                keyWords[cat_id][term]=[item_id]
            else:
                keyWords[cat_id][term]+=[item_id]                        
        
        if(CategoryItem.has_key(cat_id)==False):
            CategoryItem[cat_id]={}
            CategoryItem[cat_id][item_id]=terms_list
        else:
            CategoryItem[cat_id][item_id]=terms_list
        
        item_info+=terms_list      
        Items[item_id]=item_info
    fp_items.close()
    for cat_id in keyWords.keys():
        for key in keyWords[cat_id].keys():       
            keyWords[cat_id][key]=list(set(keyWords[cat_id][key]))
    
    lowFreTh=500  #设置要清理的低频关键词，如果小于该阈值将把该商品的该关键词删除
    largeFreTh=10000
    keyWords_filter={}
    for key1 in keyWords.keys():       
        for key2 in keyWords[key1]:
            if(len(keyWords[key1][key2])<lowFreTh)or(len(keyWords[key1][key2])>largeFreTh):
                for i in keyWords[key1][key2]:  
                    Items[i][1:]=removeAllSame(Items[i][1:],key2); #一定要注意，Items[0]是Item所属的类
                    CategoryItem[key1][i]= removeAllSame(CategoryItem[key1][i],key2);  
            else:
                if keyWords_filter.has_key(key1)==False:
                    keyWords_filter[key1]={}
                keyWords_filter[key1][key2]=keyWords[key1][key2]
    time2=time.time()
    print 'cost time:'+str(time2-time1)+' s'
    return Items,CategoryItem,ItemCategoryDic,keyWords_filter
   
#将大文件进行分割
def splitFile(filename,objFolderName,split_num):         
    fo=open(filename,'r')
    lineNum=len(fo.readlines()) #读取总共的行数
    stepLen=lineNum/split_num
    print 'lineNum:'+str(lineNum)
    fo.close()
    fo=open(filename,'r')
    for i in range(0,lineNum):
        lineStr=fo.readline()
        if(i%stepLen==0):
            index=i/stepLen            
            if index>0:
                fw.writelines(str1)
                fw.close()
            newFile =os.path.join(objFolderName,str(index)+'.txt') 
            fw=open(newFile,'w')
            str1=[lineStr]
        else:
            str1+=[lineStr]
        if (i==lineNum-1):
            fw.writelines(str1)
            fw.close()
    fo.close()
 

### 并行计算的方式读取用户的购买信息
def readUserHistory(ItemCategoryDic):
    time1=time.time()
    print '*************readUserHistory****************'
    CategoryUserbuyPerDay={} #每类商品每天购买的数量
    if os.path.exists('SPLIT')==False:#是否存在SPILT文件夹，如果不存在则创建
        os.mkdir('SPLIT')
        splitFile(USER_BUY_HISTORY,'SPLIT',1000) #分成1000份
        
    pool=Pool(THEAD_NUM)
    results=pool.map(readUserBuyHistoryPara,get_txt_paths('SPLIT'))
    pool.close()
    pool.join()
    userBuy={} 
    minTime=99999999
    maxTime=0
    for index in range(0,len(results)):
        for  user_id in results[index].keys():
            if userBuy.has_key(user_id)==False:
                userBuy[user_id]=results[index][user_id]                
            else:
                userBuy[user_id]+=results[index][user_id]
                
    #确定最大时间和最小时间 
    for user_id in userBuy.keys():
        for j in range(0,len(userBuy[user_id])):
            curTime=userBuy[user_id][j][1]
            curItem=userBuy[user_id][j][0]
            if ItemCategoryDic.has_key(curItem)==True:
                cat_id=ItemCategoryDic[curItem]
                if CategoryUserbuyPerDay.has_key(cat_id)==False: #首先判断手否有该类
                    CategoryUserbuyPerDay[cat_id]={}
                if CategoryUserbuyPerDay[cat_id].has_key(curTime)==False: #然后判读阿该类中是否有该时间的统计                   
                    CategoryUserbuyPerDay[cat_id][curTime]=1
                else:
                    CategoryUserbuyPerDay[cat_id][curTime]+=1     
            else:
                print 'Donnot have this item in ItemCategoryDic'                
                
            if(curTime>maxTime):
                maxTime=curTime
            if(curTime<minTime):
                minTime=curTime
    time2=time.time()
    print 'cost time:'+str(time2-time1)+' s'
    return userBuy,CategoryUserbuyPerDay,minTime,maxTime

### 读取要预测搭配的商品ID
def readTestData(testFileName):
    testItems=[]
    fo=open(testFileName,'r')
    lines=fo.readlines()
    for line in lines:
        testItems+=[string.atoi(line)]
    fo.close()
    return testItems
        
#####使用基于Item-to-Item的算法来对给定的item_id进行求算与之相似的item_id,minCorrValue为设置的最小相关度的值，小于该值将不做统计
def calSimilarItem(Items,CategoryItem,keyWords,item_id,minCorrValue):
    similarItems={} #字典，用来保存所有和item_id有关的item
    cat_id=Items[item_id][0]
    #item_id=2232
    if CategoryItem[cat_id].has_key(item_id)==True:
        #print 'has item_id:'+str(item_id)
        for term1 in CategoryItem[cat_id][item_id]:
            for item in keyWords[cat_id][term1]: #查找关键词表中，包含term1的所有商品ID
                if item!=item_id:                   
                    if similarItems.has_key(item)==False:#由于多个关键词会导致重复，这里去除重复                
                        value= similarFactor(CategoryItem[Items[item][0]][item],CategoryItem[cat_id][item_id])  #这部分会比较费时                
                        if value>=minCorrValue: #minCorrValue为设置的最小相关度的值，小于该值将不做统计
                            similarItems[item]=value
    return similarItems
                    
###根据达人体检搭配给出相似关系和搭配相关度
def calSimilarAndCorrPro(MatchSet):
    similarPro={}
    corrPro={}
    #计算相似度
    for key in MatchSet.keys():
        for i in range(0,len(MatchSet[key])):
            if len(MatchSet[key][i])>1:
                for m in range(0,len(MatchSet[key][i])):
                    item1=MatchSet[key][i][m]
                    for n in range(m+1,len(MatchSet[key][i])):
                        item2=MatchSet[key][i][n]
                        #添加（item1，item2）到item1的元素中
                        if similarPro.has_key(item1)==False:
                            similarPro[item1]={}
                            similarPro[item1][item2]=1
                        else:
                            if similarPro[item1].has_key(item2)==False:
                                similarPro[item1][item2]=1
                            else:
                                similarPro[item1][item2]+=1
                        #添加（item2,item1）到item1的元素中
                        if similarPro.has_key(item2)==False:
                            similarPro[item2]={}
                            similarPro[item2][item1]=1
                        else:
                            if similarPro[item2].has_key(item1)==False:                                
                                similarPro[item2][item1]=1
                            else:
                                similarPro[item2][item1]+=1    
    #计算相关性
    for key in MatchSet.keys():
        for i in range(0,len(MatchSet[key])):
            cat1=MatchSet[key][i]
            for j in range(i+1,len(MatchSet[key])):
                cat2=MatchSet[key][j]
                for m in range(0,len(cat1)):
                    item1=cat1[m]
                    for n in range(0,len(cat2)):
                        item2=cat2[n]
                        ##添加(item1,item2)到item1的元素中
                        if corrPro.has_key(item1)==False:
                            corrPro[item1]={}
                            corrPro[item1][item2]=1
                        else:
                            if corrPro[item1].has_key(item2)==False:
                                corrPro[item1][item2]=1
                            else:
                                corrPro[item1][item2]+=1
                        ##添加（item2，item1）到item2的元素中
                        if corrPro.has_key(item2)==False:
                            corrPro[item2]={}
                            corrPro[item2][item1]=1
                        else:
                            if corrPro[item2].has_key(item1)==False:
                                corrPro[item2][item1]=1
                            else:
                                corrPro[item2][item1]+=1
    return similarPro,corrPro
                                
## 根据用户购买的历史记录，计算商品的相关性和相似性
def calSimilarAndCorrUser(UserBuy,minTime,maxTime):  
    time1=time.time()
    print '*******************calSimilarAndCorrUser**************'
    timeBuySta={}
    ItemBuyHist={}  #用来存储用户购买的记录，关键词是item_id    
    ItemBuyOneMonth={}
    for user_id in UserBuy.keys():
        for i in range(0,len(UserBuy[user_id])):
            #统计每天的购买量
            curItem=UserBuy[user_id][i][0]
            curTime=UserBuy[user_id][i][1]
            if timeBuySta.has_key(curTime)==False:
                timeBuySta[curTime]=1
            else:
                timeBuySta[curTime]+=1
            #统计每个商品每个月的购买量，以计算商品间时间相关性
            maxInter=calTimeDistance(minTime,maxTime)   
            curInter=calTimeDistance(minTime,curTime)
            if ItemBuyOneMonth.has_key(curItem)==False:                
                ItemBuyOneMonth[curItem]=list(np.zeros(maxInter+1))
                ItemBuyOneMonth[curItem][curInter]+=1
            else:
                ItemBuyOneMonth[curItem][curInter]+=1
            #统计商品所被购买的情况
            if ItemBuyHist.has_key(curItem)==False:
                ItemBuyHist[curItem]=[user_id]
            else:
                ItemBuyHist[curItem]+=[user_id]  
    time2=time.time()
    print 'cost time:'+str(time2-time1)+' s'
    return timeBuySta,ItemBuyOneMonth,ItemBuyHist
###根据各个类在不同时间所购买的情况来计算不同类别的相关度
## deltaForCorr:定义计算相关度时，多长间隔天数为一个计算单元，默认为1
def calCategorySimilar(CategoryUserbuyPerDay,deltaForCorr,maxTime,minTime):
    time1=time.time()
    print '************************calCategorySimilar***********************'
    categoryBuySum={} #用来统计每个类的总购买数量，用来表明类的购买热度
    categorySimilar={} #不同类别之间的相关性以字典的方式进行存储， cat_id1,cat_id2
    totalDaysNum=calDeltaDays(maxTime,minTime)+1
    totalCatNum=len(CategoryUserbuyPerDay.keys())
    catPro=np.zeros([totalCatNum,totalDaysNum])  #用来保存每个类别在每天的购买概率
    catIndex={}     #用来存储(cat_id,cat_index)
    catProPerDelta=np.zeros([totalCatNum,int(np.ceil(totalDaysNum*1.0/deltaForCorr))]) #按照制定的
    for cat_index in  range(0,len(CategoryUserbuyPerDay.keys())):
        cat_id= CategoryUserbuyPerDay.keys()[cat_index] 
        catIndex[cat_id]=cat_index
        cat_buy_sum=sum(CategoryUserbuyPerDay[cat_id].values()) 
        categoryBuySum[cat_id]=cat_buy_sum
        for buy_time in CategoryUserbuyPerDay[cat_id].keys():
            deltaDays=calDeltaDays(buy_time,minTime)
            buy_num=CategoryUserbuyPerDay[cat_id][buy_time]
            catPro[cat_index,deltaDays]=buy_num*1.0/cat_buy_sum
            catProPerDelta[cat_index,int(np.floor(deltaDays/deltaForCorr))]+=buy_num
     
    for cat_index in range(0,len(CategoryUserbuyPerDay.keys())):
        cat_id= CategoryUserbuyPerDay.keys()[cat_index]
        catProPerDelta[cat_index,:]=catProPerDelta[cat_index,:]/sum(CategoryUserbuyPerDay[cat_id].values()) 

    for cat_1 in CategoryUserbuyPerDay.keys():
        categorySimilar[cat_1]={}
        for cat_2 in CategoryUserbuyPerDay.keys():            
            if (cat_2!=cat_1):
                categorySimilar[cat_1][cat_2]=sum(abs(catProPerDelta[catIndex[cat_1],:]-catProPerDelta[catIndex[cat_2],:]))
         
     #对结果进行排序和处理                 
    resultList=sorted(categorySimilar[cat_1].iteritems(), key=itemgetter(1), reverse=False) 
    time2=time.time()
    print 'cost time:'+str(time2-time1)+' s'
    return categoryBuySum,categorySimilar
 
    
##提交结果，只使用商品信息进行推荐，不推荐同一类，但可以推荐相似度较大的同类产品的
def matchResult(TestItems,Items,similarPro,corrPro,resultFileName):
    #万能搭配
    matchAll=[]
    for i in corrPro.keys():
        lenVal=len(corrPro[i])
        if lenVal>40: #这里的100是通过观察分布得到的，后面可以改为自适应值
            matchAll+=[[i,lenVal]] 
    matchAll= sorted(matchAll, key=itemgetter(1), reverse=True) 
    
    fp=open(resultFileName,'w')
    result={}
    proc=0
    stepLen=len(TestItems)/100
    
    for itemObj in TestItems:        
        proc+=1
        print 'index,itemObj:'+str(proc)+','+str(itemObj)
        #itemObj=2232
        if proc%stepLen==0:
            print 'processing:'+str(proc*1.0/len(TestItems))
        #计算相似度
        coutCurNum=0 #统计当前共选择的match数量
        similarObjs=calSimilarItem(Items,CategoryItem,keyWords,itemObj,0.1)
        if similarPro.has_key(itemObj)==True:
            for i in similarPro[itemObj].keys():                
                similarObjs[itemObj][i]=1#这里先忽略具体商品搭配的次数
        similarObjsList=sorted(similarObjs.iteritems(), key=itemgetter(1), reverse=True) 
        if corrPro.has_key(itemObj)==True: #判断达人推荐中是否有该商品
            for key in corrPro[itemObj].keys():
                 result[key]=99999999.0
        
        breakFactor=1.2
        for i in range(0,len(similarObjsList)):
            item1=similarObjsList[i][0]
            #print 'item1:'+str(item1)
            if (corrPro.has_key(item1)==True) and similarObjsList[i][1]>0.4: #使用那些十分相似的进行寻找相关的
                #tmpCorrPro=sorted(corrPro[item1].iteritems(), key=itemgetter(1), reverse=True)#这种方法太慢，课尝试选择随机选取的方式     
                factorNum= 6 if len(corrPro[item1].keys())>5 else len(corrPro[item1].keys())  #这里每个相似的相关商品只随机取20个           
                #print 'factorNum:'+str(factorNum)                
                for item2 in random.sample(corrPro[item1],factorNum):   
                    #print 'item1,item2：'+str(item1)+','+str(item2)
                    tmpCorr=similarObjsList[i][1]*1.0*(2-math.pow(np.e,-0.1*(corrPro[item1][item2]))) 
                    #print item1,item2,tmpCorr
                    if result.has_key(item2)==False:
                        result[item2]=tmpCorr    
                        coutCurNum+=1 
                        if(coutCurNum>=200*breakFactor):
                             print 'for3:coutCurNum>200*1.4:'+str(coutCurNum)
                             break
                    else:                        
                        if result[item2]<tmpCorr:
                            result[item2]=tmpCorr   
                    #添加搭配项 的近似项                        
                    if ((similarPro.has_key(item2)==True)and(tmpCorr>0.45))and(coutCurNum<200*breakFactor) :#对相关商品继续找相似产品进行限制
                        tmpObjsList=[]  
                        tmpSimilarNum= 10 if len(similarPro[item2].keys())>10 else len(similarPro[item2].keys())
                        for item3 in random.sample(similarPro[item2],tmpSimilarNum):                
                            tmpObjs=calSimilarItem(Items,CategoryItem,keyWords,item3,0.45)                             
                            if len(tmpObjs.keys())>0:
                                tmpObjsList=sorted(tmpObjs.iteritems(), key=itemgetter(1), reverse=True)#排序太费时间了，尤其是对已经  
                                #这里只添加前几项
                                maxTry=10 if len(tmpObjs.keys())>10 else len(tmpObjs.keys())
                                for i in range(0,maxTry):                                        
                                    item4=tmpObjsList[i][0]
                                    item4Corr=tmpCorr*tmpObjsList[i][1]
                                    if (Items[item4][0]!=Items[itemObj][0]) and item4Corr>0.4:                                           
                                        #print 'item1,item2,item3,item4,item4Corr'
                                        if (result.has_key(item4)==False):
                                            result[item4]=item4Corr  
                                            coutCurNum+=1 
                                        else:
                                            if result[item4]<item4Corr:
                                                result[item4]=item4Corr                                                                  
                    if (coutCurNum>=200*breakFactor):
                        print 'for2:coutCurNum>200*3:'+str(coutCurNum)
                        break
                if (coutCurNum>=200*breakFactor):
                    print 'for1:coutCurNum>200*3:'+str(coutCurNum)
                    break                  
        #对结果进行排序和处理                 
        resultList=sorted(result.iteritems(), key=itemgetter(1), reverse=True) 
        ## 如果相关度小于一定的值，不如直接推荐爆款
        strResult=str(itemObj)+' '
        if len(resultList)<200: #如果通过计算得到的相关值较少，则只可能通过随机选择，或者选择爆款
            print str(itemObj)+'：len(resultList)<200:'+str(len(resultList))           
            count=0
            for i in range(0,len(resultList)):                
                if i==0:
                    strResult+=str(resultList[i][0])+','
                else:
                    strResult+=str(resultList[i][0])+','
            count=len(resultList)
            for j in range(0,len(matchAll)):
                if (result.has_key(matchAll[j][0])==False)and(Items[matchAll[j][0]][0]!=Items[itemObj][0]):
                    if(count<199):
                        strResult+=str(matchAll[j][0])+','
                        count+=1
                    if count==199:
                        strResult+=str(matchAll[j][0])+'\n'
                        count+=1
                    if count>199:
                        break      
            #print str(itemObj)+':'+str(count)
            fp.writelines(strResult)
        else:            
            if resultList[200][1]<0.35: #这里是经验值，用来设置当推荐相关度较低的结果，不如推荐爆款
                print str(itemObj)+':resultList[200][1]<0.2:resultList[200][150]:'+str(resultList[200][150])
                count=0
                for i in range(0,len(resultList)):
                    if i==0:
                        strResult+=str(resultList[i][0])
                        count+=1
                    else:
                        strResult+=str(resultList[i][0])+','
                        count+=1
                    if count>180:
                        break
                for j in range(0,len(matchAll)):
                    if ((result.has_key(matchAll[j][0])==False)or(result.has_key(matchAll[j][0])and resultList.index(matchAll[j][0])>180))and(Items[matchAll[j][0]][0]!=Items[itemObj][0]):
                        if(count<199):
                            strResult+=str(matchAll[j][0])+','
                            count+=1
                        if count==199:
                            strResult+=str(matchAll[j][0])+'\n'
                            count+=1
                        if count>199:
                            break  
                fp.writelines(strResult)
            else:
                count=0
                for i in range(0,len(resultList)):
                    if i==199:
                        strResult+=str(resultList[i][0])+'\n'
                        count+=1
                    else:
                        strResult+=str(resultList[i][0])+','
                        count+=1
                    if count==200:
                        break
                fp.writelines(strResult)
    fp.close()
 
#由连续时间进行分割
def splitTime(t):
    return t/10000,(t%10000)/100,t%100
def calDeltaDays(compareTime,minTime): #计算两个时间间的天数（compareTime-minTime）
    year1,month1,day1=compareTime/10000,(compareTime%10000)/100,compareTime%100
    year2,month2,day2=minTime/10000,(minTime%10000)/100,minTime%100
    d1=datetime.date(year1,month1,day1)
    d2=datetime.date(year2,month2,day2)
    de=d1-d2
    deltaDays=int(de.total_seconds()/(3600*24))
    return deltaDays
    
def calTimeDistance(t1,t2):#计算两个时间相差的的月份，t1<t2
    if t1>t2:
        tmp=t1
        t1=t2
        t2=tmp
    year1,month1,day1=t1/10000,(t1%10000)/100,t1%100
    year2,month2,day2=t2/10000,(t2%10000)/100,t2%100
    deltaMonth=(year2-year1)*12+(month2-month1)+ (0 if day2>=day1 else -1)
    return deltaMonth
                       

#### 读取原始数据      
MatchSet= readMatchSet(MATCH_SET_FILENAME) 
Items,CategoryItem,ItemCategoryDic,keyWords=readItems(ITEMS_FILENAME)
UserBuy,CategoryUserbuyPerDay,minTime,maxTime=readUserHistory(ItemCategoryDic)  #读取用户的信息 

    
### 计算相关度和相似度
#根据商品的关键词来计算商品间的相似性，这里暂时没有使用图片信息，这里返回指定item_id的所有相似商品id


## 根据达人推荐搭配计算相似性和相关性
similarPro,corrPro=calSimilarAndCorrPro(MatchSet)
timeBuySta,ItemBuyOneMonth,ItemBuyHist=calSimilarAndCorrUser(UserBuy,minTime,maxTime)
## 根据用户购买的历史记录，计算商品的相关性和相似性


index1=5
resultFileName='fm_submissions_lzhq_'+str(index1)+'.txt'
testFileName='SplitTest/'+str(index1)+'.txt'
TestItems=readTestData(testFileName) 
matchResult(TestItems,Items,similarPro,corrPro,resultFileName)

#一次读取所有结果
resultFileName='fm_submissions_lzhq_all_0928.txt'
testFileName='test_items.txt'
TestItems=readTestData(TEST_IITEMS) 
matchResult(TestItems,Items,similarPro,corrPro,resultFileName)
#splitFile(TEST_IITEMS,'SplitTest',6)
 

finalMatch1={}
results=[]
for i in range(0,5):
    resultFileName='fm_submissions_lzhq_'+str(i)+'.txt'
    fo=open(resultFileName,'r')
    results+=[fo.readlines()]
    fo.close()
for i in range(0,len(results)):    
    for j in range(0,len(results[i])-1):
        test_id,test_result=results[i][j].split(SEPARATOR_1)
        if(finalMatch1.has_key(test_id))==True:
            print test_id
        finalMatch1[test_id]=test_result


#显示统计类的结果
cat=CategoryUserbuyPerDay.keys()
cat_id=527
x=CategoryUserbuyPerDay[cat_id].keys()
y=CategoryUserbuyPerDay[cat_id].values()
z=[]
for i in x:
    z.append(calDeltaDays(i,minTime))
plt.bar(z,y)
plt.show()

sumBuy=[]
for cat_id in CategoryUserbuyPerDay.keys():     
     sumBuy+=[sum(CategoryUserbuyPerDay[cat_id].values())]
plt.hist(sumBuy,2000)
 
510
#finalMatch2={}    
#oldResults=[]
#fo=open('fm_submissions.txt','r')
#oldResults=fo.readlines()
#fo.close()
#
#for j in range(0,len(oldResults)):
#    test_id,test_result=oldResults[j].split(SEPARATOR_1)
#    if(finalMatch2.has_key(test_id))==True:
#        print test_id
#    finalMatch2[test_id]=test_result
#
#fp=open('fm_submissions_0926.txt','w')
#finalResults=[]
#for i in range(0,len(TestItems)):
#    if finalMatch1.has_key(str(TestItems[i]))==True:
#        finalResults+=[str(TestItems[i])+' '+finalMatch1[str(TestItems[i])]]
#    else:
#        finalResults+=[str(TestItems[i])+' '+finalMatch2[str(TestItems[i])]]
#fp.writelines(finalResults) 
#fp.close()
#    
#    
    
    
    