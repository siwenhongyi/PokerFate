-- 二维向量

function bee.v2(x, y)
    return CU.Vector2(x or 0, y or 0)
    -- return {x = x or 0, y = y or 0}
end

bee.v2zero = bee.v2(0, 0)
bee.v2one = bee.v2(1, 1)

local v2c = bee.v2()
-- 缓存的向量
function bee.v2c(x, y)
    v2c.x, v2c.y = x or 0, y or 0
    return v2c
end

function bee.v2Sub(a, b)
    return bee.v2(a.x - b.x, a.y - b.y)
end

function bee.v2Add(a, b)
    return bee.v2(a.x + b.x, a.y + b.y)
end

function bee.v2Mul(a, s)
    return bee.v2(a.x * s, a.y * s)
end

function bee.v2Angle(a, b)
    return CU.Vector2.Angle(a, b)
end

function bee.v2Distance(a, b)
    return CU.Vector2.Distance(a, b)
end

function bee.v2Dot(a, b)
    return CU.Vector2.Dot(a, b)
end

function bee.v2Lerp(a, b, t)
    return CU.Vector2.Lerp(a, b, t)
end

function bee.v2Scale(a, b)
    return CU.Vector2.v2Scale(a, b)
end

function bee.v2SignedAngle(a, b)
    return CU.Vector2.SignedAngle(a, b)
end

function bee.v2Normalize(a)
    a:Normalize()
    return a
end


-- 三维向量
function bee.v3(x, y, z)
    return CU.Vector3(x or 0, y or 0, z or 0)
    -- return {x = x or 0, y = y or 0, z = z or 0}
end

bee.v3zero = bee.v3(0, 0, 0)
bee.v3one = bee.v3(1, 1, 1)

local v3c = bee.v3()
-- 缓存的向量
function bee.v3c(x, y, z)
    v3c.x, v3c.y, v3c.z = x or 0, y or 0, z or 0
    return v3c
end

function bee.v3BetweenPoint(a,b,percent)
	if not percent then
		percent=0.5
	end
	local normal = bee.v3Sub(b,a)
	normal=bee.v3Normalize(normal)
	local distance = bee.v3Distance(a, b)
    return normal * (distance * percent) + a
end

function bee.v3GetVerticalDir(a,b)
	local _dir=bee.v3Sub(a,b)
	if _dir.x == 0 then
		return bee.v3(1, 0, 0)
	else
	    return bee.v3Normalize(bee.v3(_dir.y ,-_dir.x, 0))	
	end
end

function bee.v3Sub(a, b)
    return bee.v3(a.x - b.x, a.y - b.y, a.z - b.z)
end

function bee.v3Add(a, b)
    return bee.v3(a.x + b.x, a.y + b.y, a.z + b.z)
end

function bee.v3Mul(a, s)
    return bee.v3(a.x * s, a.y * s, a.z * s)
end

function bee.v3Angle(a, b)
    return CU.Vector3.Angle(a, b)
end

function bee.v3Distance(a, b)
    return CU.Vector3.Distance(a, b)
end

function bee.v3Cross(a, b)
    return CU.Vector3.Cross(a, b)
end

function bee.v3Dot(a, b)
    return CU.Vector3.Dot(a, b)
end

function bee.v3Lerp(a, b, t)
    return CU.Vector3.Lerp(a, b, t)
end

function bee.v3Scale(a, b)
    return CU.Vector3.v3Scale(a, b)
end

function bee.v3SignedAngle(a, b)
    return CU.Vector3.SignedAngle(a, b)
end

function bee.v3Normalize(a)
    a:Normalize()
    return a
end

-- color
function bee.colorHex(hex)
    local len = string.len(hex)
    if len < 7 then
        return CU.Color(1, 1, 1)
    end
    if string.sub(hex, 1, 1) ~= '#' then
        return CU.Color(1, 1, 1)
    end
    return CU.Color(
        tonumber(string.sub(hex, 2, 3), 16) / 255,
        tonumber(string.sub(hex, 4, 5), 16) / 255,
        tonumber(string.sub(hex, 6, 7), 16) / 255,
        len == 9 and tonumber(string.sub(hex, 8, 9), 16) or 1
    )
