-- lbase64加密和解密算法
--Lua--十进制转二进制
function dec_to_binary (data)
    local dst = ""
    local remainder, quotient

    --异常处理
    if not data then return dst end                 --源数据为空
    if not tonumber(data) then return dst end       --源数据无法转换为数字

    --如果源数据是字符串转换为数字
    if "string" == type(data) then
        data = tonumber(data)
    end

    while true do
        quotient = math.floor(data / 2)
        remainder = data % 2
        dst = dst..remainder
        data = quotient
        if 0 == quotient then
            break
        end
    end

    --翻转
    dst = string.reverse(dst)

    --补齐8位
    if 8 > #dst then
        for i = 1, 8 - #dst, 1 do
            dst = '0'..dst
        end
    end
    return dst
end

--Lua--二进制转十进制
function binary_to_dec (data)
    local dst = 0
    local tmp = 0

    --异常处理
    if not data then return dst end                 --源数据为空
    if not tonumber(data) then return dst end       --源数据无法转换为数字

    --如果源数据是字符串去除前面多余的0
    if "string" == type(data) then
        data = tostring(tonumber(data))
    end

    --如果源数据是数字转换为字符串
    if "number" == type(data) then
        data = tostring(data)
    end

    --转换
    for i = #data, 1, -1 do
        tmp = tonumber(data:sub(-i, -i))
        if 0 ~= tmp then
            for j = 1, i - 1, 1 do
                tmp = 2 * tmp
            end
        end
        dst = dst + tmp
    end
    return dst
end

--Lua--base64加密
function base64encode(data)
    local basecode = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
    local code = ""
    local dst = ""
    local tmp
    local encode_num = 0            --base64编码后的分组数，6字节为一组
    local num = 0                   --编码后后缀"="的个数
    local len = 1                   --用于统计编码个数，76个编码字符换行

    --异常处理
    if not data then return dst end                 --源数据为空

    --转换为二进制
    for i = 1, #data, 1 do
        tmp = data:byte(i)
        if 0 > tmp or 255 < tmp then
            return dst
        end
        code = code..dec_to_binary(tmp)
    end

    --字符串长度不能被3整除的情况
    num = 3 - #data % 3
    if 0 < num then
        for i = 1, num, 1 do
            code = code.."00000000"
        end
    end

    encode_num = #code / 6

    --开始编码
    for i = 1, #code, 6 do
        tmp = binary_to_dec(code:sub(i, i + 5))
        tmp = tmp + 1                                              --Lua下标从1开始，切记

        if 0 == num then                                           --无"="后缀的情况
            dst = dst..basecode:sub(tmp, tmp)
            len = len + 1
            encode_num = encode_num - 1
            --每76个字符换行
            if 76 == len then
                dst = dst.."\n"
                len = 1
            end
        end

        if 0 < num then                                            --有"="后缀的情况
            if encode_num == num and 1 == tmp then
                dst = dst..'='
                len = len + 1
                encode_num = encode_num - 1
                num = num - 1
                --每76个字符换行
                if 76 == len then
                    dst = dst.."\n"
                    len = 1
                end
        else
            dst = dst..basecode:sub(tmp, tmp)
            len = len + 1
            encode_num = encode_num - 1
            --每76个字符换行
            if 76 == len then
                dst = dst.."\n"
                len = 1
            end
        end
        end
    end
    return dst
end

--Lua--base64解密
function base64decode(data)
    local basecode = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
    local dst = ""
    local code = ""
    local tmp, index

    --异常处理
    if not data then return dst end                   --源数据为空

    data = data:gsub("\n", "")                        --去除换行符
    data = data:gsub("=", "")                         --去除'='

    for i = 1, #data, 1 do
        tmp = data:sub(i, i)
        index = basecode:find(tmp)
        if nil == index then
            return dst
        end
        index = index - 1
        tmp = dec_to_binary(index)
        code = code..tmp:sub(3)                       --去除前面多余的两个'00'
    end

    --开始解码
    for i = 1, #code, 8 do
        tmp = string.char(binary_to_dec(code:sub(i, i + 7)))
        if nil ~= tmp then
            dst = dst..tmp
        end
    end
    return dst
end

base64 = {
    encode = base64encode,
    decode = base64decode,
}