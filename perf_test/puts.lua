math.randomseed(os.time())

request = function()
    param_value = math.random(1,1000000000)
    param_value2 = math.random(1,1000000000)
    path = "/?short=t" .. param_value .. param_value2.. "&long=http://test"
    return wrk.format("PUT", path)
end